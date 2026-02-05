# 🐍 Clash of Code - Backend

The robust API and real-time socket server for **Clash of Code**. Handles authentication, gamification logic, and global chat messaging.

## ⚡ Technologies

- `Django 6`
- `Django REST Framework`
- `Django Channels`
- `PostgreSQL`
- `Supabase`
- `Docker`
- `JWT`
- `Daphne`

## 🚀 Key Features

- **RESTful API** - Comprehensive endpoints for user profiles, XP tracking, and tasks.
- **WebSocket Server** - Real-time bidirectional communication for global chat.
- **OAuth System** - Integrated social login for GitHub, Google, and Discord.
- **Background Tasks** - Efficient handling of asynchronous operations.

## 🛠️ Installation & Setup

1. **Run with Docker**:
    The backend services are fully containerized. You do not need to manage local virtual environments.

    ```bash
    docker-compose up --build
    ```

    API: `http://127.0.0.1:8000` | WebSockets: `ws://127.0.0.1:8000/ws/`

## 🔐 Environment Variables

Create a `.env` file in this directory:

```env
SECRET_KEY=your_secret_key
DEBUG=True
DATABASE_URL=postgresql://...
SUPABASE_URL=...
SUPABASE_KEY=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
# ... other OAuth keys
```

## 📂 Project Structure

| Directory | Description |
| :--- | :--- |
| `authentication/` | Auth logic, OAuth views, and User models. |
| `chat/` | WebSocket consumers and routing. |
| `project/` | Core Django settings and configuration. |
| `templates/` | Server-rendered templates (if any). |
