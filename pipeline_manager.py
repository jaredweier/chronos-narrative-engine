import gc
try:
    import torch as _torch
    _HAS_TORCH = True
except ImportError:
    _torch = None
    _HAS_TORCH = False
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError
from typing import Callable, Any, Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import threading
import time

from logger import get_logger

logger = get_logger("pipeline_manager")

_gpu_lock = threading.Lock()


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineError(Exception):
    pass


@dataclass
class Job:
    id: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    future: Optional[Future] = None
    vram_start: float = 0.0
    vram_end: float = 0.0
    vram_peak: float = 0.0
    cancelled: bool = False


@dataclass
class VramSnapshot:
    allocated_mb: float
    reserved_mb: float
    peak_mb: float
    timestamp: float

    @classmethod
    def now(cls) -> "VramSnapshot":
        if _HAS_TORCH and _torch.cuda.is_available():
            return cls(
                allocated_mb=_torch.cuda.memory_allocated() / 1048576,
                reserved_mb=_torch.cuda.memory_reserved() / 1048576,
                peak_mb=_torch.cuda.max_memory_allocated() / 1048576,
                timestamp=time.time(),
            )
        return cls(allocated_mb=0.0, reserved_mb=0.0, peak_mb=0.0, timestamp=time.time())


class VramBudgetTracker:
    def __init__(self, budget_fraction: float = 0.85):
        self._budget_fraction = budget_fraction
        self._history: List[VramSnapshot] = []
        self._snapshots: Dict[str, List[VramSnapshot]] = {}
        self._peak_overall_mb: float = 0.0

    @property
    def budget_bytes(self) -> int:
        if not (_HAS_TORCH and _torch.cuda.is_available()):
            return 0
        total = _torch.cuda.get_device_properties(0).total_memory
        return int(total * self._budget_fraction)

    @property
    def budget_mb(self) -> float:
        return self.budget_bytes / 1048576

    @property
    def current_allocated_mb(self) -> float:
        if not (_HAS_TORCH and _torch.cuda.is_available()):
            return 0.0
        return _torch.cuda.memory_allocated() / 1048576

    @property
    def usage_fraction(self) -> float:
        if not (_HAS_TORCH and _torch.cuda.is_available()):
            return 0.0
        total = _torch.cuda.get_device_properties(0).total_memory
        allocated = _torch.cuda.memory_allocated()
        return allocated / total if total > 0 else 0.0

    @property
    def headroom_mb(self) -> float:
        return max(0.0, self.budget_mb - self.current_allocated_mb)

    @property
    def has_headroom(self) -> bool:
        return self.usage_fraction < self._budget_fraction

    def snapshot(self, label: str = "") -> VramSnapshot:
        s = VramSnapshot.now()
        self._history.append(s)
        if label:
            self._snapshots.setdefault(label, []).append(s)
        if s.allocated_mb > self._peak_overall_mb:
            self._peak_overall_mb = s.allocated_mb
        return s

    def get_job_vram_usage(self, job_id: str) -> Dict[str, float]:
        snaps = self._snapshots.get(job_id, [])
        if len(snaps) < 2:
            return {}
        start = snaps[0]
        end = snaps[-1]
        return {
            "start_mb": start.allocated_mb,
            "end_mb": end.allocated_mb,
            "delta_mb": end.allocated_mb - start.allocated_mb,
            "peak_mb": max(s.allocated_mb for s in snaps),
            "reserved_end_mb": end.reserved_mb,
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "budget_mb": self.budget_mb,
            "current_allocated_mb": self.current_allocated_mb,
            "usage_fraction": self.usage_fraction,
            "headroom_mb": self.headroom_mb,
            "has_headroom": self.has_headroom,
            "peak_overall_mb": self._peak_overall_mb,
            "total_snapshots": len(self._history),
        }


class PipelineManager:
    def __init__(self, max_workers: int = 2, vram_budget_fraction: float = 0.85):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()
        self._job_counter = 0
        self.vram = VramBudgetTracker(budget_fraction=vram_budget_fraction)

    def _generate_job_id(self) -> str:
        with self._lock:
            self._job_counter += 1
            return f"job_{self._job_counter}_{int(time.time())}"

    def submit_job(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        with self._lock:
            if not self.vram.has_headroom:
                raise PipelineError(
                    f"VRAM budget exceeded ({self.vram.usage_fraction:.1%} used). "
                    f"Wait for current jobs to complete or reduce load."
                )
            job_id = self._generate_job_id()
            job = Job(id=job_id, func=func, args=args, kwargs=kwargs)

        def run_job():
            start_snap = self.vram.snapshot(job_id)
            job.vram_start = start_snap.allocated_mb
            job.status = JobStatus.RUNNING
            try:
                if job.cancelled:
                    job.status = JobStatus.FAILED
                    job.error = "Job cancelled"
                    return None
                result = func(*args, **kwargs)
                if job.cancelled:
                    job.status = JobStatus.FAILED
                    job.error = "Job cancelled"
                    return None
                job.result = result
                job.status = JobStatus.COMPLETED
                return result
            except Exception as e:
                job.error = str(e)
                job.status = JobStatus.FAILED
                logger.error("Job %s failed: %s", job_id, e)
                raise
            finally:
                with _gpu_lock:
                    gc.collect()
                    if _HAS_TORCH and _torch.cuda.is_available():
                        _torch.cuda.empty_cache()
                        _torch.cuda.synchronize()
                end_snap = self.vram.snapshot(job_id)
                job.vram_end = end_snap.allocated_mb
                usage = self.vram.get_job_vram_usage(job_id)
                job.vram_peak = usage.get("peak_mb", 0.0)
                logger.debug(
                    "Job %s VRAM: start=%.0fMB end=%.0fMB peak=%.0fMB",
                    job_id, job.vram_start, job.vram_end, job.vram_peak,
                )

        future = self.executor.submit(run_job)
        job.future = future

        with self._lock:
            self.jobs[job_id] = job

        return job_id

    def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> Any:
        job = self._get_job_safe(job_id)
        if job is None or job.future is None:
            return None
        try:
            return job.future.result(timeout=timeout)
        except FutureTimeoutError:
            logger.warning("Job %s timed out after %ss", job_id, timeout)
            raise PipelineError(f"Job {job_id} timed out after {timeout}s")
        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e)
            raise PipelineError(f"Job {job_id} failed: {e}") from e

    def _get_job_safe(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self.jobs.get(job_id)

    def clear_vram_guardrail(self) -> None:
        with _gpu_lock:
            gc.collect()
            if _HAS_TORCH and _torch.cuda.is_available():
                _torch.cuda.empty_cache()
                _torch.cuda.synchronize()
        self.vram.snapshot("clear_vram_guardrail")

    def cancel_job(self, job_id: str) -> bool:
        job = self._get_job_safe(job_id)
        if job is None:
            return False
        job.cancelled = True
        if job.future is not None and job.future.running():
            cancelled = job.future.cancel()
            return cancelled
        return True

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Dict[str, Any]]:
        with self._lock:
            jobs = list(self.jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return [
            {
                "id": j.id,
                "status": j.status.value,
                "error": j.error,
                "cancelled": j.cancelled,
            }
            for j in jobs
        ]

    def shutdown(self, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait)

    def get_vram_summary(self) -> Dict[str, Any]:
        return self.vram.summary()

    def get_job_vram_report(self, job_id: str) -> Dict[str, float]:
        return self.vram.get_job_vram_usage(job_id)


pipeline_instance = None
_pipeline_lock = threading.Lock()


def get_pipeline() -> PipelineManager:
    global pipeline_instance
    if pipeline_instance is None:
        with _pipeline_lock:
            if pipeline_instance is None:
                from config import PIPELINE_MAX_WORKERS, VRAM_BUDGET_FRACTION
                pipeline_instance = PipelineManager(
                    max_workers=PIPELINE_MAX_WORKERS,
                    vram_budget_fraction=VRAM_BUDGET_FRACTION,
                )
    return pipeline_instance


def submit_pdf_and_transcribe(pdf_path: str, video_path: str, initial_prompt: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    from pdf_parser import parse_zuercher_pdf
    from transcriber import transcribe_bodycam
    from config import WHISPER_INITIAL_PROMPT

    pipeline = get_pipeline()
    pdf_job_id = pipeline.submit_job(parse_zuercher_pdf, pdf_path)
    prompt = initial_prompt or WHISPER_INITIAL_PROMPT
    video_job_id = pipeline.submit_job(transcribe_bodycam, video_path, initial_prompt=prompt)

    try:
        cad_data = pipeline.wait_for_job(pdf_job_id, timeout=120)
    except PipelineError:
        logger.exception("PDF parsing job failed")
        cad_data = None

    try:
        transcript = pipeline.wait_for_job(video_job_id, timeout=300)
    except PipelineError:
        logger.exception("Transcription job failed")
        transcript = None

    return cad_data, transcript


def cleanup_pipeline() -> None:
    global pipeline_instance
    if pipeline_instance is not None:
        pipeline_instance.clear_vram_guardrail()
        pipeline_instance.shutdown(wait=True)
        pipeline_instance = None
        logger.info("Pipeline manager shut down")


if __name__ == '__main__':
    print("Pipeline Manager initialized")
    print("Max workers: 2")
    print("VRAM guardrail: Active")
