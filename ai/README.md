# 🤖 Clash of Code - AI Service

The **AI Service** provides advanced intelligence and tutor features to the platform. Built with **FastAPI** and **LangChain**, it implements a **RAG (Retrieval-Augmented Generation)** architecture to help users solve coding challenges based on project-specific documentation.

## 🚀 Tech Stack

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
- **Orchestration:** [LangChain](https://www.langchain.com/)
- **Vector Database:** [ChromaDB](https://www.trychroma.com/)
- **LLM Support:** OpenAI & HuggingFace integration
- **Embeddings:** Sentence-Transformers

## 📂 Project Structure

- `main.py`: Entry point for the FastAPI application.
- `llm_factory.py`: Factory pattern for initializing different LLM providers.
- `prompts.py`: Centralized management of system and user prompts.
- `config.py`: Configuration management using Pydantic Settings and `.env`.
- `logger_config.py`: Structured logging setup.

## 🛠️ Key Features

- **RAG-Powered Tutor:** Answers user queries by retrieving relevant context from a knowledge base.
- **Code Assistance:** Helps users debug and optimize their code during challenges.
- **Provider Agnostic:** Easily switch between OpenAI, HuggingFace, or local LLMs via configuration.
- **Streaming Responses:** Supports real-time streaming for a better user experience.

## 🔧 Setup & Installation

### Prerequisites
- Python 3.11+
- ChromaDB (running as a service or local)

### Local Development
1. **Navigate to the AI service:**
   ```bash
   cd services/ai
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Variables:**
   Configure `.env` with required keys:
   - `CORE_SERVICE_URL`
   - `INTERNAL_API_KEY`
   - `GROQ_API_KEY`
   - `OPENAI_API_BASE`
   - `MODEL_NAME`
   - `EMBEDDING_MODEL`
   - `CHROMA_SERVER_HOST`
   - `CHROMA_SERVER_HTTP_PORT`

4. **Start the service:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8002 --reload
   ```

## 📡 API Endpoints

- `POST /hints`: Generate challenge hint guidance.
- `POST /analyze`: Generate code review feedback.
- `GET /health`: Health check endpoint.
- `GET /docs`: Interactive Swagger documentation.
