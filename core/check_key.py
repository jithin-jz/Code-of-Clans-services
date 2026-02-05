
from django.conf import settings
import jwt
from datetime import datetime, timezone

try:
    print(f"Loading private key...")
    priv_key = settings.JWT_PRIVATE_KEY
    print(f"Private Key length: {len(priv_key)}")
    print(f"First 50 chars: {priv_key[:50]}")
    
    print("Attempting to sign test token...")
    payload = {"user_id": 1, "exp": datetime.now(timezone.utc)}
    token = jwt.encode(payload, priv_key, algorithm="RS256")
    print("Token signed successfully!")
    print(f"Token: {token[:20]}...")
    
except Exception as e:
    print(f"ERROR: {e}")
