# 💬 Chat & Real-Time Service (FastAPI)

A high-concurrency WebSocket server handling all real-time interactions, including room-based messaging and global system notifications.

## ✨ Features

- **WebSockets**: Permanent bidirectional connections for instant messaging.
- **Redis Pub/Sub**: Scales horizontal delivery across multiple pod instances.
- **Stateless Auth**: Verifies user identity via shared JWT Public Key.
- **Notification Types**:
  - Global Announcement (broadcast).
  - Room Messages (targeted).
  - Personal System Alerts (private).

## 🚀 Running Local

```bash
cd services/chat
pip install -r requirements.txt

# Start the service
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

## 🔌 WebSocket API

**URL**: `ws://api-coc.jithin.site/ws/{room_name}/?token={JWT}`

### Example Message Protocol (JSON)

```json
{
  "content": "Hello World!",
  "type": "message"
}
```

---

## 🏗️ Architecture

1. **Connection**: Client establishes WS connection with a JWT.
2. **Auth**: The service decodes the JWT using the `JWT_PUBLIC_KEY` (No DB query required).
3. **Tracking**: Active connections are stored in memory (`ConnectionManager`).
4. **Broadcast**: Messages are published to Redis, and all listening instances relay to their connected clients.

---

## 📂 Structure

- `main.py`: App initialization and route definitions.
- `manager.py`: Logic for managing active WebSocket connections.
- `auth.py`: JWT verification logic using asymmetric keys.
- `redis_client.py`: Redis Pub/Sub integration.
