import pytest
from utils import extract_json, safe_filename


def test_extract_json_plain():
    result = extract_json('{"key": "value"}')
    assert result == '{"key": "value"}'


def test_extract_json_codeblock():
    result = extract_json('```json\n{"key": "value"}\n```')
    assert result == '{"key": "value"}'


def test_extract_json_nested():
    result = extract_json('{"a": {"b": ["c", "d"]}}')
    assert result == '{"a": {"b": ["c", "d"]}}'


def test_extract_json_no_json():
    result = extract_json("Just plain text with no JSON")
    assert result == ""


def test_extract_json_with_string_braces():
    result = extract_json('{"text": "has {braces} inside"}')
    assert result == '{"text": "has {braces} inside"}'


def test_safe_filename_basic():
    assert safe_filename("hello.txt") == "hello.txt"


def test_safe_filename_spaces():
    assert safe_filename("my file.pdf") == "my_file.pdf"


def test_safe_filename_special_chars():
    assert safe_filename("file:test?name.doc") == "file_test_name.doc"


def test_safe_filename_path_traversal():
    assert safe_filename("../../etc/passwd") == "passwd"
