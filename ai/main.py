import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# ChromaDB workaround for some systems
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

load_dotenv()

app = FastAPI(
    title="AI Service",
    version="1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://core:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE") # Optional, for Groq/LocalLLM
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")

class HintRequest(BaseModel):
    user_code: str
    challenge_slug: str
    language: str = "python"
    hint_level: int = 1  # 1: Vague, 2: Moderate, 3: Specific
    user_xp: int = 0

@app.get("/health")
def health():
    return {"status": "ok"}

from big_bang import run_big_bang

@app.post("/big-bang")
async def trigger_big_bang(background_tasks: BackgroundTasks, levels: int = 5):
    """
    Triggers the autonomous curriculum generation in the background.
    """
    background_tasks.add_task(run_big_bang, levels)
    return {"message": f"Big Bang started for {levels} levels. Check AI logs for progress."}

@app.post("/generate-level")
async def generate_single_level(background_tasks: BackgroundTasks, level: int, user_id: int = None):
    """
    Generates a specific single level in the background.
    """
    def _run_single(lvl, uid):
        from auto_generator import AutoGenerator
        import requests
        
        logger.info(f"Generating Single Level {lvl} for User {uid}...")
        try:
            generator = AutoGenerator()
            challenge_json = generator.generate_level(lvl, user_id=uid)
            
            headers = {
                "X-Internal-API-Key": INTERNAL_API_KEY,
                "Content-Type": "application/json"
            }
            url = f"{CORE_SERVICE_URL}/api/challenges/"
            challenge_json["order"] = lvl
            if uid:
                challenge_json["created_for_user_id"] = uid
            
            response = requests.post(url, json=challenge_json, headers=headers)
            if response.status_code in [200, 201]:
                logger.info(f"Level {lvl} generated and saved successfully for user {uid}.")
            else:
                logger.error(f"Failed to save Level {lvl}: {response.text}")
        except Exception as e:
            logger.error(f"Error generating single level {lvl}: {e}")

    background_tasks.add_task(_run_single, level, user_id)
    return {"message": f"Generation started for level {level}"}

import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize RAG Components
CHROMA_PATH = "chroma_db"
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings)

@app.post("/hints")
def generate_hint(request: HintRequest):
    logger.info(f"Received hint request for challenge: {request.challenge_slug}")
    
    if not OPENAI_API_KEY or "placeholder" in OPENAI_API_KEY:
        logger.error("OpenAI API Key not configured")
        raise HTTPException(status_code=500, detail="OpenAI API Key not configured")

    # 1. Fetch Challenge Context from Core Service
    headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
    try:
        url = f"{CORE_SERVICE_URL}/api/challenges/{request.challenge_slug}/context/"
        logger.info(f"Fetching context from: {url}")
        
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
             logger.error(f"Core service error: {response.status_code} - {response.text}")
             # If Core returns 404, the challenge slug is likely wrong or missing context
             raise HTTPException(status_code=response.status_code, detail=f"Core service returned {response.status_code}")
        
        context_data = response.json()
        logger.info("Context fetched successfully")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Core Service: {e}")
        raise HTTPException(status_code=503, detail="Core service unavailable")

    # 2. Construct Prompt
    description = context_data.get("description", "")
    test_code = context_data.get("test_code", "")
    
    # 2. RAG: Search for similar challenges
    logger.info("Performing similarity search for RAG...")
    similar_docs = []
    try:
        query = f"Challenge: {description}\nUser Code: {request.user_code}"
        results = vector_db.similarity_search(query, k=2)
        similar_docs = [doc.page_content for doc in results if doc.metadata.get("slug") != request.challenge_slug]
    except Exception as e:
        logger.warning(f"RAG Search failed: {e}. Proceeding without extra context.")

    # 3. Construct Prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert coding tutor. Your goal is to provide a helpful hint to a student who is stuck on a coding challenge. "
                   "Do NOT give the direct solution. Analyze their code and the challenge requirements. "
                   "Identify the error or misconception.\n\n"
                   "CONTEXT ENRICHMENT (RAG):\n"
                   "Below are patterns from similar challenges to help you provide a better hint:\n"
                   "{rag_context}\n\n"
                   "ADAPTIVITY RULES:\n"
                   "1. Skill Level: The user has {user_xp} XP. (0-500: Novice, 501-2000: Intermediate, 2000+: Advanced). "
                   "Adjust your vocabulary and explanation depth accordingly.\n"
                   "2. Progressive Depth: This is Level {hint_level} of assistance (1: Strategy/Vague, 2: Logic/Moderate, 3: Implementation/Specific). "
                   "Level 1 should be a gentle nudge. Level 3 can guide them to the exact line or syntax but still not solve it entirely.\n\n"
                   "Be encouraging and concise."),
        ("user", "Challenge Description:\n{description}\n\n"
                 "Test Code:\n{test_code}\n\n"
                 "Student's Code:\n{user_code}\n\n"
                 "Provide a Level {hint_level} hint:")
    ])

    # 4. Call LLM
    try:
        logger.info(f"Initializing LLM with model: {MODEL_NAME}")
        llm = ChatOpenAI(
            api_key=OPENAI_API_KEY, 
            model=MODEL_NAME,
            base_url=OPENAI_API_BASE
        ) 
        
        chain = prompt | llm | StrOutputParser()
    
        logger.info("Invoking LLM chain")
        hint = chain.invoke({
            "description": description,
            "test_code": test_code,
            "user_code": request.user_code,
            "hint_level": request.hint_level,
            "user_xp": request.user_xp,
            "rag_context": "\n\n".join(similar_docs) if similar_docs else "No similar patterns found."
        })
        logger.info("Hint generated successfully")
    except Exception as e:
         logger.error(f"LLM Error: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail="Error generating hint")

    return {"hint": hint}
