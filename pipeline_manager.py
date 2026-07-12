import gc
import torch
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
import threading
import time


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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


class PipelineManager:
    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._job_counter = 0
    
    def _generate_job_id(self) -> str:
        with self._lock:
            self._job_counter += 1
            return f"job_{self._job_counter}_{int(time.time())}"
    
    def submit_job(self, func: Callable, *args, **kwargs) -> str:
        job_id = self._generate_job_id()
        job = Job(id=job_id, func=func, args=args, kwargs=kwargs)
        
        def run_job():
            job.status = JobStatus.RUNNING
            try:
                result = func(*args, **kwargs)
                job.result = result
                job.status = JobStatus.COMPLETED
                return result
            except Exception as e:
                job.error = str(e)
                job.status = JobStatus.FAILED
                raise
            finally:
                self.clear_vram_guardrail()
        
        future = self.executor.submit(run_job)
        job.future = future
        
        with self._lock:
            self.jobs[job_id] = job
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            
            return {
                "id": job.id,
                "status": job.status.value,
                "result": job.result,
                "error": job.error
            }
    
    def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> Any:
        with self._lock:
            job = self.jobs.get(job_id)
        
        if job is None or job.future is None:
            return None
        
        result = job.future.result(timeout=timeout)
        return result
    
    def submit_parallel(self, tasks: list[tuple[Callable, tuple, dict]]) -> list[str]:
        job_ids = []
        for func, args, kwargs in tasks:
            job_id = self.submit_job(func, *args, **kwargs)
            job_ids.append(job_id)
        return job_ids
    
    def wait_for_all(self, job_ids: list[str], timeout: Optional[float] = None) -> list[Any]:
        results = []
        for job_id in job_ids:
            try:
                result = self.wait_for_job(job_id, timeout)
                results.append(result)
            except Exception as e:
                results.append(None)
        return results
    
    def clear_vram_guardrail(self):
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    def shutdown(self, wait: bool = True):
        self.executor.shutdown(wait=wait)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            status_counts = {}
            for job in self.jobs.values():
                status = job.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "total_jobs": len(self.jobs),
                "by_status": status_counts,
                "max_workers": self.max_workers
            }


pipeline_instance = None
_pipeline_lock = threading.Lock()


def get_pipeline() -> PipelineManager:
    global pipeline_instance
    if pipeline_instance is None:
        with _pipeline_lock:
            if pipeline_instance is None:
                pipeline_instance = PipelineManager(max_workers=2)
    return pipeline_instance


def submit_pdf_and_transcribe(pdf_path: str, video_path: str) -> tuple[str, str]:
    from pdf_parser import parse_zuercher_pdf
    from transcriber import transcribe_bodycam
    
    pipeline = get_pipeline()
    
    pdf_job_id = pipeline.submit_job(parse_zuercher_pdf, pdf_path)
    video_job_id = pipeline.submit_job(transcribe_bodycam, video_path)
    
    cad_data = pipeline.wait_for_job(pdf_job_id, timeout=120)
    transcript = pipeline.wait_for_job(video_job_id, timeout=300)
    
    return cad_data, transcript


def cleanup_pipeline():
    global pipeline_instance
    if pipeline_instance is not None:
        pipeline_instance.clear_vram_guardrail()
        pipeline_instance.shutdown(wait=False)
        pipeline_instance = None


if __name__ == '__main__':
    print("Pipeline Manager initialized")
    print("Max workers: 2")
    print("VRAM guardrail: Active")
