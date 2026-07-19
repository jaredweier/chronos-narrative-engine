import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pipeline_manager import (
    PipelineManager, PipelineError, VramBudgetTracker, VramSnapshot,
    cleanup_pipeline,
)


@pytest.fixture(autouse=True)
def _reset_pipeline():
    yield
    cleanup_pipeline()


class MockDeviceProps:
    total_memory = 8 * 1073741824


def _mock_cuda_is_available():
    return True


def _mock_cuda_get_device_properties(_device):
    return MockDeviceProps


class TestVramSnapshot:
    def test_snapshot_without_cuda(self):
        s = VramSnapshot.now()
        assert s.allocated_mb == 0.0
        assert s.reserved_mb == 0.0
        assert s.peak_mb == 0.0
        assert s.timestamp > 0


class TestVramBudgetTracker:
    def test_init_defaults(self):
        t = VramBudgetTracker(0.85)
        assert t._budget_fraction == 0.85

    def test_budget_bytes_zero_without_cuda(self):
        t = VramBudgetTracker()
        assert t.budget_bytes == 0

    def test_current_allocated_mb_zero_without_cuda(self):
        t = VramBudgetTracker()
        assert t.current_allocated_mb == 0.0

    def test_usage_fraction_zero_without_cuda(self):
        t = VramBudgetTracker()
        assert t.usage_fraction == 0.0

    def test_headroom_no_cuda(self):
        t = VramBudgetTracker()
        assert t.headroom_mb == 0.0

    def test_has_headroom_no_cuda(self):
        t = VramBudgetTracker()
        assert t.has_headroom is True

    def test_snapshot_no_cuda(self):
        t = VramBudgetTracker()
        s = t.snapshot("test")
        assert s.allocated_mb == 0.0
        assert len(t._history) == 1

    def test_snapshot_with_label(self):
        t = VramBudgetTracker()
        t.snapshot("label1")
        assert len(t._snapshots["label1"]) == 1

    def test_get_job_vram_usage_insufficient_snapshots(self):
        t = VramBudgetTracker()
        result = t.get_job_vram_usage("no_snaps")
        assert result == {}

    def test_get_job_vram_usage_with_snapshots(self):
        t = VramBudgetTracker()
        t.snapshot("job1")
        time.sleep(0.001)
        t.snapshot("job1")
        result = t.get_job_vram_usage("job1")
        assert "start_mb" in result
        assert "end_mb" in result
        assert "delta_mb" in result
        assert "peak_mb" in result

    def test_summary(self):
        t = VramBudgetTracker()
        s = t.summary()
        assert "budget_mb" in s
        assert "headroom_mb" in s
        assert "has_headroom" in s
        assert "total_snapshots" in s
        assert s["total_snapshots"] == 0

    def test_peak_overall_mb_tracks(self):
        t = VramBudgetTracker()
        t.snapshot()
        assert t._peak_overall_mb >= 0


class TestPipelineManager:
    def test_init_defaults(self):
        p = PipelineManager(max_workers=2)
        assert p.max_workers == 2
        assert p.vram._budget_fraction == 0.85

    def test_submit_job_basic(self):
        p = PipelineManager(max_workers=2)
        job_id = p.submit_job(lambda x: x + 1, 41)
        assert job_id.startswith("job_")
        result = p.wait_for_job(job_id, timeout=5)
        assert result == 42

    def test_submit_job_failure(self):
        p = PipelineManager(max_workers=2)

        def fail():
            raise ValueError("boom")

        job_id = p.submit_job(fail)
        with pytest.raises(PipelineError, match="boom"):
            p.wait_for_job(job_id, timeout=5)

    def test_wait_for_nonexistent_job(self):
        p = PipelineManager(max_workers=2)
        result = p.wait_for_job("nonexistent")
        assert result is None

    def test_vram_report_available(self):
        p = PipelineManager(max_workers=2)
        job_id = p.submit_job(lambda: 42)
        p.wait_for_job(job_id, timeout=5)
        summary = p.get_vram_summary()
        assert "budget_mb" in summary
        assert "current_allocated_mb" in summary

    def test_clear_vram_guardrail(self):
        p = PipelineManager(max_workers=2)
        p.clear_vram_guardrail()
        assert len(p.vram._history) >= 1

    def test_shutdown(self):
        p = PipelineManager(max_workers=2)
        p.shutdown(wait=True)

    def test_get_pipeline_singleton(self):
        from pipeline_manager import get_pipeline, pipeline_instance, _pipeline_lock
        with _pipeline_lock:
            old = pipeline_instance
        inst = get_pipeline()
        assert inst is not None
        inst2 = get_pipeline()
        assert inst is inst2


class TestJobVramTracking:
    def test_job_records_vram_values(self):
        p = PipelineManager(max_workers=2)

        def dummy():
            return 99

        job_id = p.submit_job(dummy)
        p.wait_for_job(job_id, timeout=5)
        job = p._get_job_safe(job_id)
        assert job is not None
        assert job.vram_start >= 0
        assert job.vram_end >= 0
        assert job.vram_peak >= 0
