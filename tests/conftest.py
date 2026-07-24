import pytest

MOCK_AI_DRAFT = "old version of report with some text"
MOCK_CORRECTED = "new and improved version of the report with more text"

MOCK_TRANSCRIPT_SEGMENTS = [
    {
        "start": 0.0,
        "end": 5.0,
        "text": "hello world",
        "confidence_tier": "high",
        "words": [
            {"word": "hello", "start": 0.0, "end": 2.0, "probability": 0.95},
            {"word": "world", "start": 2.1, "end": 4.5, "probability": 0.96}
        ]
    },
    {
        "start": 5.0,
        "end": 10.0,
        "text": "unclear audio",
        "confidence_tier": "low",
        "words": [
            {"word": "unclear", "start": 5.1, "end": 7.0, "probability": 0.40},
            {"word": "audio", "start": 7.1, "end": 9.5, "probability": 0.45}
        ]
    }
]

@pytest.fixture
def mock_pairs_fixture():
    return [
        {
            "incident_id": "INC001",
            "officer_name": "Officer A",
            "document_type": "DUI",
            "ai_draft": MOCK_AI_DRAFT,
            "corrected": MOCK_CORRECTED
        }
    ]

import pytest
import psycopg2

def pytest_runtest_setup(item):
    if 'database' in item.nodeid or 'auth' in item.nodeid or 'integration' in item.nodeid:
        try:
            conn = psycopg2.connect('dbname=chronos dbname=chronos host=localhost port=5432 user=user password=password')
            conn.close()
        except Exception:
            pytest.skip('Postgres server not running, skipping database tests.')
