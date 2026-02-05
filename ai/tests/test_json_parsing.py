
import pytest
from auto_generator import extract_json_from_response

def test_clean_json():
    response = '{"key": "value"}'
    assert extract_json_from_response(response) == '{"key": "value"}'

def test_markdown_json():
    response = '```json\n{"key": "value"}\n```'
    assert extract_json_from_response(response) == '{"key": "value"}'

def test_markdown_no_lang():
    response = '```\n{"key": "value"}\n```'
    assert extract_json_from_response(response) == '{"key": "value"}'

def test_surrounding_text():
    response = 'Here is the JSON:\n```json\n{"key": "value"}\n```\nHope it helps!'
    assert extract_json_from_response(response) == '{"key": "value"}'

def test_regex_fallback():
    # Only if the function supports it (it does in the code I read)
    response = 'Some text {"key": "value"} some more text'
    assert extract_json_from_response(response) == '{"key": "value"}'
