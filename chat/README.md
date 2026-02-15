# 💬 Clash of Code - Chat Service

The **Chat Service** enables real-time communication between users on the platform. It leverages **FastAPI's WebSocket** support and **Redis Pub/Sub** to provide a scalable, low-latency messaging experience.

## 🚀 Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Communication:** WebSockets
- **State Management:** Redis (Pub/Sub and Caching)
- **Database:** PostgreSQL (via [SQLModel](https://sqlmodel.tiangolo.com/))
- **Security:** JWT Authentication

## 📂 Project Structure

- `main.py`: WebSocket manager and route handlers.
- `models.py`: SQLModel definitions for chat messages and rooms.
- `schemas.py`: Pydantic models for request/response validation.
- `rate_limiter.py`: In-memory and Redis-backed rate limiting for messages.
- `database.py`: Session management for the chat database.

## 🛠️ Key Features

- **Real-Time Messaging:** Instant message delivery via WebSockets.
- **Global & Private Channels:** Support for different chat contexts.
- **Message Persistence:** Chat history is stored in a dedicated PostgreSQL database.
- **Security:** Endpoints and WebSocket connections are secured with JWT from the Core service.
- **Rate Limiting:** Protects the service from spam and abuse.

## 🔧 Setup & Installation

### Prerequisites
- Python 3.11+
- Redis
- PostgreSQL (Chat DB)

### Local Development
1. **Navigate to the Chat service:**
   ```bash
   cd services/chat
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Variables:**
   Configure `.env` with:
   - `DATABASE_URL` (PostgreSQL connection string)
   - `REDIS_URL`
   - `JWT_SECRET` (Must match Core service secret)

4. **Start the service:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

## 📡 WebSocket Protocol

Connect to `ws://localhost/ws/chat/{room_id}` with a valid JWT in the headers or as a query parameter.
- **Format:** JSON
- **Events:** `message`, `join`, `leave`, `typing`
