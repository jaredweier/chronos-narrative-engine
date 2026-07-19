import sys
import pytest
from unittest.mock import patch, MagicMock

# Inject mock requests module before importing health so check_ollama can import it
_mock_requests = MagicMock()
sys.modules['requests'] = _mock_requests

from health import (
    HealthCheck, check_ollama, check_dirs, check_database, check_whisper, run_all_checks,
)


def test_healthcheck_icon_ok():
    hc = HealthCheck("test", True, "ok", "ok")
    assert hc.icon() == "\u2705"


def test_healthcheck_icon_error():
    hc = HealthCheck("test", False, "error", "error")
    assert hc.icon() == "\u26A0"


def test_healthcheck_icon_warning():
    hc = HealthCheck("test", False, "warning", "warning")
    assert hc.icon() == "\u26A0"


def test_check_ollama_ok():
    _mock_requests.get.return_value.status_code = 200
    _mock_requests.get.return_value.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
    result = check_ollama()
    assert result.status is True
    assert result.severity == "ok"


def test_check_ollama_model_missing():
    _mock_requests.get.return_value.status_code = 200
    _mock_requests.get.return_value.json.return_value = {"models": [{"name": "other-model"}]}
    result = check_ollama()
    assert result.status is False
    assert result.severity == "error"


def test_check_ollama_connection_refused():
    _mock_requests.get.side_effect = ConnectionError("Connection refused")
    result = check_ollama()
    assert result.status is False


@patch("health.os.makedirs")
@patch("health.os.access")
@patch("health.shutil.disk_usage")
def test_check_dirs_ok(mock_du, mock_access, mock_makedirs):
    mock_access.return_value = True
    mock_du.return_value.free = 10 * 1024 ** 3
    results = check_dirs()
    assert len(results) == 3
    for r in results:
        assert r.status is True


@patch("health.os.makedirs")
@patch("health.os.access")
@patch("health.shutil.disk_usage")
def test_check_dirs_not_writable(mock_du, mock_access, mock_makedirs):
    mock_access.return_value = False
    mock_du.return_value.free = 10 * 1024 ** 3
    results = check_dirs()
    assert any(not r.status for r in results)


@patch("health.os.makedirs")
@patch("health.os.access")
@patch("health.shutil.disk_usage")
def test_check_dirs_low_space(mock_du, mock_access, mock_makedirs):
    mock_access.return_value = True
    mock_du.return_value.free = 500 * 1024 ** 2
    results = check_dirs()
    assert all(r.status for r in results)


@patch("health.os.makedirs")
@patch("health.os.access")
@patch("health.shutil.disk_usage")
def test_run_all_checks(mock_du, mock_access, mock_makedirs):
    _mock_requests.get.return_value.status_code = 200
    _mock_requests.get.return_value.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
    mock_access.return_value = True
    mock_du.return_value.free = 10 * 1024 ** 3
    with patch("health.check_database") as mock_db:
        mock_db.return_value = HealthCheck("Database", True, "ok", "ok")
        with patch("health.check_whisper") as mock_whisper:
            mock_whisper.return_value = HealthCheck("Whisper", True, "ok", "ok")
            results = run_all_checks()
            assert len(results) >= 3


@patch("health.os.makedirs")
@patch("health.os.access")
@patch("health.shutil.disk_usage")
def test_check_database_via_health(mock_du, mock_access, mock_makedirs):
    _mock_requests.get.return_value.status_code = 200
    _mock_requests.get.return_value.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
    mock_access.return_value = True
    mock_du.return_value.free = 10 * 1024 ** 3
    with patch("database.get_db_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [5]
        mock_conn.return_value.__enter__.return_value.execute.return_value = mock_cursor
        result = check_database()
        assert result.status is True
        assert "5 records" in result.message
