# Code of Clans - Services

Microservices architecture for the Code of Clans platform.

## Architecture

| Service | Technology | Role |
| :--- | :--- | :--- |
| **core** | Django / DRF | Main API, Auth, Database Orchestration, Payments |
| **chat** | FastAPI / WebSockets | Real-time chat, Notifications, User presence |
| **ai** | FastAPI / LangChain | AI Challenge Generation, Code Sandbox (Piston) |

## Tech Stack (Shared)
- **Database**: PostgreSQL (Core)
- **Cache/Broker**: Redis
- **Containerization**: Docker & Docker Compose
- **API Documentation**: Swagger/OpenAPI

## Development

All services are orchestrated via Docker Compose in the root directory.

```bash
docker-compose up --build
```

### Internal Communication
Services communicate via REST APIs and are protected by an `X-Internal-API-Key`.
