import subprocess
import tempfile
import os
import logging

logger = logging.getLogger(__name__)

def verify_challenge(solution_code: str, test_code: str):
    """
    Runs the provided solution against the test code in a temporary sandbox.
    Returns (success: bool, error_message: str)
    """
    # Merge solution and tests
    # We add a preamble to ensure standard libraries are available
    full_code = f"{solution_code}\n\n{test_code}"
    
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w') as tmp:
        tmp.write(full_code)
        tmp_path = tmp.name

    try:
        # Run the code using a subprocess with a timeout to prevent infinite loops
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            text=True,
            timeout=5  # 5 second timeout for safety
        )
        
        if result.returncode == 0:
            return True, ""
        else:
            # Capture the traceback but keep it concise
            error = result.stderr.split("Traceback")[-1] if "Traceback" in result.stderr else result.stderr
            return False, error.strip()
            
    except subprocess.TimeoutExpired:
        return False, "Execution timed out (Possible infinite loop detected)"
    except Exception as e:
        return False, str(e)
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Quick self-test
    sol = "def add(a, b): return a + b"
    test = "assert add(2, 3) == 5"
    ok, err = verify_challenge(sol, test)
    print(f"Self-test: {'PASS' if ok else 'FAIL (' + err + ')'}")
