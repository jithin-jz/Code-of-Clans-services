# 🏰 Code of Clans - Core Service

The **Core Service** is the backbone of the Code of Clans platform. Built with **Django** and **Django REST Framework (DRF)**, it manages user authentication, challenge logic, payments, rewards, and notification systems.

## 🚀 Tech Stack

- **Framework:** [Django 5.0](https://www.djangoproject.com/)
- **API:** [Django REST Framework](https://www.django-rest-framework.org/)
- **Database:** PostgreSQL
- **Task Queue:** Celery + Redis
- **Documentation:** drf-spectacular (Swagger/OpenAPI 3.0)
- **Payments:** Razorpay Integration

## 📂 Project Structure

The service is organized into modular Django apps:

- `users/`: Custom user model, profile management, and authentication logic.
- `auth/`: Social OAuth integrations (GitHub, Google, Discord).
- `challenges/`: Core game logic, level management, and code execution validation.
- `rewards/`: XP system, badges, and certificate generation.
- `payments/`: Razorpay order processing and transaction history.
- `posts/`: Community features, image sharing, and social interactions.
- `notifications/`: Real-time system notifications and alerts.
- `administration/`: Enhanced admin dashboard logic.

## 🛠️ Key Features

- **Gamified Learning:** Progress through levels, earn XP, and unlock badges.
- **Social Integration:** Share your progress, like posts, and compete on leaderboards.
- **Asynchronous Processing:** Celery handles heavy tasks like certificate generation and email notifications.
- **Secure Payments:** Integrated Razorpay for premium features and items.

## 🔧 Setup & Installation

### Prerequisites
- Python 3.11+
- Redis
- PostgreSQL

### Local Development
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd services/core
   ```
2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\\Scripts\\activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables:**
   Copy `.env.example` to `.env` and fill in your credentials.
5. **Run Migrations:**
   ```bash
   python manage.py migrate
   ```
6. **Start the server:**
   ```bash
   python manage.py runserver 8000
   ```

## 📡 API Documentation

Once the server is running, access the interactive API docs at:
- **Swagger UI:** `http://localhost:8000/api/docs/`
- **Redoc:** `http://localhost:8000/api/redoc/`

## 👷 Worker Commands

- **Start Celery Worker:**
  ```bash
  celery -A project worker --loglevel=info
  ```
- **Start Celery Beat:**
  ```bash
  celery -A project beat --loglevel=info
  ```
