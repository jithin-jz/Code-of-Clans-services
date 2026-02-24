import os
import pytest
import json
import asyncio
from starlette.websockets import WebSocketDisconnect

# Set dummy environment variables BEFORE importing main app
os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_PUBLIC_KEY"] = "dummy_key"

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from main import app, manager

client = TestClient(app)

@pytest.mark.asyncio
@patch("main.verify_jwt")
@patch("main.rate_limiter")
async def test_websocket_auth_failure(mock_limiter, mock_verify):
    mock_verify.return_value = None
    
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            "/ws/chat/general",
            headers={"authorization": "Bearer invalid"},
        ) as websocket:
            pass
    assert exc.value.code == 1008

@pytest.mark.asyncio
@patch("main.verify_jwt")
@patch("main.rate_limiter")
@patch("main.redis_client")
@patch("main.sessionmaker")
@patch("main.dynamo_client")
async def test_websocket_success_flow(mock_dynamo, mock_sessionmaker, mock_redis, mock_limiter, mock_verify):
    # Setup Auth
    mock_verify.return_value = {"user_id": 1, "username": "testuser"}
    
    # Setup Rate Limiter
    mock_limiter.check_connection_rate = AsyncMock(return_value=True)
    mock_limiter.check_message_rate = AsyncMock(return_value=True)
    mock_limiter.check_burst_rate = AsyncMock(return_value=True)
    
    # Setup DB History (empty)
    mock_session = AsyncMock()
    mock_sessionmaker.return_value.return_value.__aenter__.return_value = mock_session
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    # Mock Redis (Sync container)
    mock_redis.publish = AsyncMock()
    
    # Mock pubsub for subscriber task
    # Note: .pubsub() is a sync call in redis-py
    mock_pubsub = MagicMock() 
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    
    # Mock listen to be an async generator
    async def empty_gen():
        if False: yield None
    mock_pubsub.listen.return_value = empty_gen()
    
    # Force .pubsub() to return our mock_pubsub directly (not a coroutine)
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)

    # Mock Dynamo
    mock_dynamo.save_message = AsyncMock()

    with client.websocket_connect(
        "/ws/chat/general",
        headers={"authorization": "Bearer valid"},
    ) as websocket:
        # Send a message
        websocket.send_text(json.dumps({"message": "hello world"}))
        
    # Verify side effects
    # 1. SQL Save
    mock_session.add.assert_called()
    # 2. Dynamo Save
    mock_dynamo.save_message.assert_called()
    # 3. Redis Publish (Presence + Message)
    assert mock_redis.publish.call_count >= 2
