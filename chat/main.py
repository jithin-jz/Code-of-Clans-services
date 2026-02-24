from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, Request
from fastapi.responses import JSONResponse
import os, json, jwt, asyncio, logging
import redis.asyncio as redis
from dotenv import load_dotenv
from typing import Dict, List
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from schemas import ChatMessage as ChatMessageSchema, PresenceEvent, IncomingMessage
from database import init_db, engine
from models import ChatMessage
from rate_limiter import RateLimiter
from dynamo import dynamo_client

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# --------------------------------------------------
# Config
# --------------------------------------------------

app = FastAPI(title="Chat Service")

# JWT Configuration (RS256 - asymmetric)
ALGORITHM = "RS256"
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
JWT_ACCESS_COOKIE_NAME = os.getenv("JWT_ACCESS_COOKIE_NAME", "access_token")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
rate_limiter = RateLimiter(redis_client)

# Chat config
HISTORY_LIMIT = 50
TYPING_INDICATOR_TTL = 3  # seconds

@app.on_event("startup")
async def on_startup():
    await init_db()
    await dynamo_client.create_table_if_not_exists()

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return JSONResponse(content={"status": "ok", "service": "chat"}, status_code=status.HTTP_200_OK)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        content={"error": "Internal server error"},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

@app.get("/history/{room}")
async def get_message_history(
    request: Request,
    room: str,
    limit: int = 50,
    offset: int = 0,
):
    """Get paginated message history for a room."""
    token = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        token = request.cookies.get(JWT_ACCESS_COOKIE_NAME)
    # Verify token
    payload = verify_jwt(token or "")
    if not payload:
        return JSONResponse(
            content={"error": "Invalid token"},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    try:
        # Try fetching from DynamoDB first for high performance
        messages = await dynamo_client.get_messages(room, limit=limit)
        
        if messages:
            return JSONResponse(
                content={
                    "messages": [
                        {
                            "username": msg["sender"],
                            "message": msg["content"],
                            "timestamp": msg["timestamp"],
                            "reactions": msg.get("reactions", {})
                        }
                        for msg in reversed(messages) # Dynamo returns latest first, we want chronological
                    ],
                    "has_more": len(messages) == limit,
                    "source": "dynamodb"
                },
                status_code=status.HTTP_200_OK
            )

        # Fallback to SQL if Dynamo is empty (migration period)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            # Get messages with pagination
            statement = (
                select(ChatMessage)
                .where(ChatMessage.room == room)
                .order_by(ChatMessage.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await session.execute(statement)
            messages = result.scalars().all()
            
            # Reverse to get chronological order
            messages = list(reversed(messages))
            
            return JSONResponse(
                content={
                    "messages": [
                        {
                            "username": msg.username,
                            "message": msg.message,
                            "timestamp": msg.timestamp.isoformat(),
                            "reactions": msg.reactions or {}
                        }
                        for msg in messages
                    ],
                    "has_more": len(messages) == limit,
                    "source": "sql"
                },
                status_code=status.HTTP_200_OK
            )
    except Exception as e:
        logger.error(f"Error fetching message history: {e}", exc_info=True)
        return JSONResponse(
            content={"error": "Failed to fetch message history"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def verify_jwt(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            JWT_PUBLIC_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp"]},
        )
        if payload.get("type") != "access":
            return None
        if "user_id" not in payload:
            return None
        return payload
    except jwt.PyJWTError:
        return None


def channel_key(room: str) -> str:
    return f"chat:room:{room}"


# --------------------------------------------------
# Connection Managers
# --------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, ws: WebSocket, room: str):
        await ws.accept()
        self.active.setdefault(room, []).append(ws)

        # Start subscriber if first connection
        if len(self.active[room]) == 1 and room not in self.tasks:
             self.tasks[room] = asyncio.create_task(self.redis_subscriber(room))

    async def disconnect(self, ws: WebSocket, room: str):
        if room in self.active and ws in self.active[room]:
            self.active[room].remove(ws)
            
            # Cleanup if room empty
            if not self.active[room]:
                self.active.pop(room, None)
                if room in self.tasks:
                    self.tasks[room].cancel()
                    try:
                        await self.tasks[room]
                    except asyncio.CancelledError:
                        pass
                    self.tasks.pop(room, None)

    async def redis_subscriber(self, room: str):
        """Subscribes to Redis channel and broadcasts to local websockets."""
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel_key(room))

        try:
            async for event in pubsub.listen():
                if event["type"] == "message":
                    payload = json.loads(event["data"])
                    await self.broadcast_local(room, payload)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel_key(room))
            raise

    async def broadcast_local(self, room: str, payload: dict):
        dead = []
        message = json.dumps(payload)

        for ws in self.active.get(room, []):
            try:
                await ws.send_text(message)
            except ConnectionResetError:
                logger.warning(f"Connection reset while broadcasting to room {room}")
                dead.append(ws)
            except RuntimeError as e:
                logger.error(f"Runtime error broadcasting to room {room}: {e}")
                dead.append(ws)
            except Exception as e:
                logger.error(f"Unexpected error broadcasting to room {room}: {e}", exc_info=True)
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws, room)


manager = ConnectionManager()

class NotificationManager:
    def __init__(self):
        self.active: Dict[int, List[WebSocket]] = {}
        self.tasks: Dict[int, asyncio.Task] = {}

    async def connect(self, ws: WebSocket, user_id: int):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)
        
        if len(self.active[user_id]) == 1 and user_id not in self.tasks:
            self.tasks[user_id] = asyncio.create_task(self.notification_subscriber(user_id))
            logger.info(f"Started notification subscriber for user {user_id}")

    async def disconnect(self, ws: WebSocket, user_id: int):
        if user_id in self.active and ws in self.active[user_id]:
            self.active[user_id].remove(ws)
            if not self.active[user_id]:
                self.active.pop(user_id, None)
                if user_id in self.tasks:
                    self.tasks[user_id].cancel()
                    try:
                        await self.tasks[user_id]
                    except asyncio.CancelledError:
                        pass
                    self.tasks.pop(user_id, None)
                    logger.info(f"Stopped notification subscriber for user {user_id}")

    async def notification_subscriber(self, user_id: int):
        pubsub = redis_client.pubsub()
        channel = f"notifications_{user_id}"
        await pubsub.subscribe(channel)

        try:
            async for event in pubsub.listen():
                if event["type"] == "message":
                    payload = json.loads(event["data"])
                    await self.broadcast_user(user_id, payload)
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)
            raise
        except Exception as e:
            logger.error(f"Error in notification subscriber for user {user_id}: {e}")
            await pubsub.unsubscribe(channel)

    async def broadcast_user(self, user_id: int, payload: dict):
        dead = []
        message = json.dumps(payload)
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws, user_id)

notification_manager = NotificationManager()

# --------------------------------------------------
# WebSocket Endpoints
# --------------------------------------------------

@app.websocket("/ws/chat/{room}")
async def chat_ws(ws: WebSocket, room: str):
    # ---- Auth ----
    token = None
    
    # Fallback to header (for non-browser clients)
    auth = ws.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = ws.cookies.get(JWT_ACCESS_COOKIE_NAME)

    if not token:
        logger.warning(f"WebSocket connection rejected: no token (room={room})")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = verify_jwt(token)
    if not payload:
        logger.warning(f"WebSocket connection rejected: invalid JWT (room={room})")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["user_id"]
    username = payload.get("username", f"user-{user_id}")
    avatar_url = payload.get("avatar_url")

    # ---- Rate Limit: Connection ----
    if not await rate_limiter.check_connection_rate(user_id):
        logger.warning(f"WebSocket rate limited: user_id={user_id}")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # ---- Connect ----
    await manager.connect(ws, room)

    # ---- Send history from DB ----
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    history_data = []
    try:
        async with async_session() as session:
            statement = (
                select(ChatMessage)
                .where(ChatMessage.room == room)
                .order_by(ChatMessage.timestamp.desc())
                .limit(HISTORY_LIMIT)
            )
            result = await session.execute(statement)
            messages = result.scalars().all()
            # Front end expects oldest first
            history_data = [
                {
                    "room": m.room,
                    "message": m.message,
                    "user_id": m.user_id,
                    "username": m.username,
                    "avatar_url": m.avatar_url,
                    "timestamp": m.timestamp.isoformat(),
                    "reactions": m.reactions or {}
                }
                for m in reversed(messages)
            ]
    except SQLAlchemyError as e:
        logger.error("Failed to load chat history for room %s: %s", room, e)

    if history_data:
        await ws.send_text(json.dumps({
            "type": "history",
            "messages": history_data,
        }))

    # ---- Presence join ----
    join = PresenceEvent(
        event="join",
        user_id=user_id,
        username=username,
        avatar_url=avatar_url,
        count=len(manager.active.get(room, [])),
    )
    await redis_client.publish(channel_key(room), join.model_dump_json())

    # ---- Message loop ----
    try:
        while True:
            raw = await ws.receive_text()

            incoming = IncomingMessage.model_validate_json(raw)

            # ---- Rate Limit: Message ----
            if not await rate_limiter.check_message_rate(user_id):
                # Send rate limit warning to user
                await ws.send_json({"type": "error", "message": "Rate limited: too many messages"})
                continue
            
            if not await rate_limiter.check_burst_rate(user_id):
                # Send burst limit warning
                await ws.send_json({"type": "error", "message": "Slow down! Too many messages too fast"})
                continue

            message = ChatMessageSchema(
                room=room,
                message=incoming.message,
                user_id=user_id,
                username=username,
                avatar_url=avatar_url,
            )

            # Persist to DB (SQL & DynamoDB)
            db_msg = ChatMessage(
                room=room,
                message=message.message,
                user_id=message.user_id,
                username=message.username,
                avatar_url=message.avatar_url,
            )
            
            # Save to SQL
            async with async_session() as session:
                session.add(db_msg)
                await session.commit()

            # Save to DynamoDB for high-speed history retrieval
            try:
                await dynamo_client.save_message(
                    room_id=room,
                    sender=username,
                    message=incoming.message,
                    user_id=user_id
                )
            except Exception as e:
                logger.error(f"Failed to save message to DynamoDB: {e}")
                # We continue anyway to ensure real-time broadcast works

            # Publish
            await redis_client.publish(
                channel_key(room),
                message.model_dump_json(),
            )

    except WebSocketDisconnect:
        await manager.disconnect(ws, room)

        leave = PresenceEvent(
            event="leave",
            user_id=user_id,
            username=username,
            avatar_url=avatar_url,
            count=len(manager.active.get(room, [])),
        )
        await redis_client.publish(channel_key(room), leave.model_dump_json())


@app.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket):
    # ---- Auth ----
    token = None
    auth = ws.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = ws.cookies.get(JWT_ACCESS_COOKIE_NAME)
    
    if not token:
        logger.warning("Notification WebSocket connection rejected: no token")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = verify_jwt(token)
    if not payload:
        logger.warning("Notification WebSocket connection rejected: invalid JWT")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload["user_id"]

    # ---- Connect ----
    await notification_manager.connect(ws, user_id)

    # ---- Keep alive loop ----
    try:
        while True:
            # Just wait for messages or disconnection
            await ws.receive_text()
    except WebSocketDisconnect:
        await notification_manager.disconnect(ws, user_id)
