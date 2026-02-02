import requests
import os
from dotenv import load_dotenv

# Load env variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
API_URL = "http://localhost:8002/hints"  # URL when running locally or via docker port mapping

def test_generate_hint():
    if not OPENAI_API_KEY or "placeholder" in OPENAI_API_KEY:
        print("Skipping test: OPENAI_API_KEY not set.")
        return

    payload = {
        "user_code": "print(hello)",
        "challenge_slug": "hello-world",
        "language": "python"
    }
    
    # Note: This test assumes the Core service is also running and accessible
    # or relies on the AI service to handle connection errors gracefully.
    
    try:
        response = requests.post(API_URL, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    print("Running AI Hint Test...")
    test_generate_hint()
