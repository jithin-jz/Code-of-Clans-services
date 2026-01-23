from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
import os, json, jwt, asyncio
import redis.asyncio as redis
from dotenv import load_dotenv
from typing import Dict, List

from schemas import ChatMessage as ChatMessageSchema, PresenceEvent, IncomingMessage
from database import init_db, engine
from models import ChatMessage
from sqlmodel import select
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

load_dotenv()

# --------------------------------------------------
# Config
# --------------------------------------------------

app = FastAPI(title="Advanced Chat Service")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

HISTORY_LIMIT = 50

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
from fastapi.responses import JSONResponse

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp"]},
        )
    except jwt.PyJWTError:
        return None


def history_key(room: str) -> str:
    return f"chat:history:{room}"


def channel_key(room: str) -> str:
    return f"chat:room:{room}"


# --------------------------------------------------
# Connection Manager
# --------------------------------------------------

# --------------------------------------------------
# Connection Manager
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
                del self.active[room]
                if room in self.tasks:
                    self.tasks[room].cancel()
                    try:
                        await self.tasks[room]
                    except asyncio.CancelledError:
                        pass
                    del self.tasks[room]

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
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws, room)


manager = ConnectionManager()

# --------------------------------------------------
# WebSocket Endpoint
# --------------------------------------------------

@app.websocket("/ws/chat/{room}")
async def chat_ws(ws: WebSocket, room: str):
    # ---- Auth ----
    token = ws.query_params.get("token")
    print(f"Connection attempt: room={room}, token_present={bool(token)}")
    
    # Fallback to header (for non-browser clients)
    if not token:
        auth = ws.headers.get("authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            print("Found token in header")

    if not token:
        print("No token found")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = verify_jwt(token)
    if not payload:
        print("Invalid JWT")
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    print(f"Auth success: {payload.get('username')}")
    print(f"Token Payload: {payload}")
    if payload.get("avatar_url"):
        print(f"Avatar found: {payload['avatar_url']}")
    else:
        print("Avatar NOT found in token")

    user_id = payload["user_id"]
    username = payload.get("username", f"user-{user_id}")
    avatar_url = payload.get("avatar_url")

    # ---- Connect ----
    await manager.connect(ws, room)

    # ---- Send history from DB ----
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        statement = select(ChatMessage).where(ChatMessage.room == room).order_by(ChatMessage.timestamp.desc()).limit(HISTORY_LIMIT)
        result = await session.exec(statement)
        messages = result.all()
        # Front end expects oldest first
        history_data = [
            {
                "room": m.room,
                "message": m.message,
                "user_id": m.user_id,
                "username": m.username,
                "avatar_url": m.avatar_url,
                "timestamp": m.timestamp.isoformat()
            }
            for m in reversed(messages)
        ]

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

            message = ChatMessageSchema(
                room=room,
                message=incoming.message,
                user_id=user_id,
                username=username,
                avatar_url=avatar_url,
            )

            # Persist to DB
            db_msg = ChatMessage(
                room=room,
                message=message.message,
                user_id=message.user_id,
                username=message.username,
                avatar_url=message.avatar_url,
            )
            async with async_session() as session:
                session.add(db_msg)
                await session.commit()

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
