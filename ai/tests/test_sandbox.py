
import pytest
import asyncio
from sandbox import is_safe_code, verify_challenge

def test_security_check_valid_code():
    code = "x = 1\ny = x + 1\nprint(y)"
    result = is_safe_code(code)
    assert result["safe"] is True
    assert result["error"] is None

def test_security_check_blocked_import():
    code = "import os\nos.system('echo hack')"
    result = is_safe_code(code)
    assert result["safe"] is False
    assert "Importing 'os' is not allowed" in result["error"]

def test_security_check_blocked_builtin():
    code = "exec('print(1)')"
    result = is_safe_code(code)
    assert result["safe"] is False
    assert "Calling function 'exec' is not allowed" in result["error"]

@pytest.mark.asyncio
async def test_verify_challenge_execution_success():
    # Pass running code
    user_code = "def solution(x): return x * 2"
    test_code = "assert solution(2) == 4"
    result = await verify_challenge(user_code, test_code)
    assert result["passed"] is True
    assert result["error"] is None

@pytest.mark.asyncio
async def test_verify_challenge_execution_failure():
    # Fail running code
    user_code = "def solution(x): return x + 1"
    test_code = "assert solution(2) == 4" # 2+1 != 4
    result = await verify_challenge(user_code, test_code)
    assert result["passed"] is False
    assert "Tests Failed" in result["error"]
