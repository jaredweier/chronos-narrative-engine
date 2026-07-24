import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import unittest.mock
import os
import asyncio

import vision_parser

@patch("subprocess.run")
@patch("os.listdir")
def test_extract_frames(mock_listdir, mock_run):
    # Mocking os.listdir to return fake frames
    mock_listdir.return_value = ["frame_0001.jpg", "frame_0002.jpg", "not_a_frame.txt"]
    
    frames = vision_parser.extract_frames("dummy.mp4", fps=1)
    
    assert len(frames) == 2
    assert frames[0].endswith("frame_0001.jpg")
    mock_run.assert_called_once()

class MockContextManager:
    async def __aenter__(self):
        mock_resp = AsyncMock()
        mock_resp.json.return_value = {"response": "A person walking"}
        return mock_resp
    async def __aexit__(self, exc_type, exc, tb):
        pass

def test_fetch_description():
    mock_session = MagicMock()
    mock_session.post.return_value = MockContextManager()
    
    with patch("builtins.open", unittest.mock.mock_open(read_data=b"fake")):
        desc = asyncio.run(vision_parser._fetch_description(mock_session, "dummy.jpg"))
        assert desc == "A person walking"

@patch("vision_parser._describe_frames_async", new_callable=AsyncMock)
def test_describe_frames(mock_describe_async):
    mock_describe_async.return_value = ["Desc 1", "Desc 2"]
    result = vision_parser.describe_frames(["frame1.jpg", "frame2.jpg"])
    assert result == "Desc 1\nDesc 2"

@patch("vision_parser.VISION_ENABLE_FACIAL_REC", True)
@patch("vision_parser.VISION_ENABLE_ALPR", True)
@patch("vision_parser.detect_faces")
@patch("vision_parser.detect_license_plates")
def test_extract_entities(mock_alpr, mock_faces):
    mock_faces.return_value = [{"type": "face", "box": [0,0,10,10], "score": 0.9}]
    mock_alpr.return_value = [{"type": "license_plate", "text": "ABC1234", "box": [20,20,50,50], "score": 0.95}]
    
    results = vision_parser.extract_entities(["frame1.jpg"])
    
    assert "frame1.jpg" in results
    entities = results["frame1.jpg"]
    assert len(entities) == 2
    assert entities[0]["type"] == "face"
    assert entities[1]["type"] == "license_plate"

@patch("vision_parser.VISION_ENABLE_ACTION_REC", True)
@patch("vision_parser.logger")
def test_recognize_actions_import_fallback(mock_logger):
    # Test fallback when decord/transformers are missing
    with patch.dict('sys.modules', {'decord': None, 'transformers': None}):
        results = vision_parser.recognize_actions("dummy.mp4")
        assert results == []


