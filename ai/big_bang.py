import os
import requests
import logging
import time
from auto_generator import AutoGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://core:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")

def run_big_bang(target_levels=10):
    """
    The Orchestrator: Wipes the DB and generates levels from 1 to target_levels.
    """
    generator = AutoGenerator()
    
    # 1. PURGE (We'll assume the user runs the purge command separately or we call an endpoint)
    # For safety, let's assume we call the core API's internal purge if we add one, 
    # but for now, we expect the user to have run 'purge_levels'
    
    logger.info(f"Starting Big Bang Generation for {target_levels} levels...")
    
    success_count = 0
    for i in range(1, target_levels + 1):
        try:
            logger.info(f"--- Processing Level {i} ---")
            challenge_json = generator.generate_level(i)
            
            # 2. POST TO CORE
            # We need to make sure the Core service has a way to receive this without a CSRF/Auth token
            # We'll use the Internal-API-Key
            headers = {
                "X-Internal-API-Key": INTERNAL_API_KEY,
                "Content-Type": "application/json"
            }
            
            # Note: We need to add this endpoint to ChallengeViewSet or use the standard one with internal bypass
            url = f"{CORE_SERVICE_URL}/api/challenges/" # Standard create endpoint
            
            # Add order and slug explicitly if not in JSON
            challenge_json["order"] = i
            
            response = requests.post(url, json=challenge_json, headers=headers)
            
            if response.status_code in [201, 200]:
                logger.info(f"Level {i} SAVED to Core Service.")
                success_count += 1
            else:
                logger.error(f"Failed to save Level {i}: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Critical error in Big Bang at Level {i}: {str(e)}")
            continue

    logger.info(f"Big Bang COMPLETE. {success_count}/{target_levels} levels created.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # Run the first 5 levels as a test
    run_big_bang(5)
