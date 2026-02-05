import os
import sys
import logging
from typing import Optional
import httpx

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Local imports
from config import settings
# Lazy imports for big_bang and auto_generator to avoid potential circular/init issues if any
from big_bang import run_big_bang
from prompts import HINT_GENERATION_SYSTEM_PROMPT, HINT_GENERATION_USER_TEMPLATE

# Configure Logging
from logger_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)



load_dotenv()

# Initialize App
app = FastAPI(
    title="AI Service",
    version="1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Components
# Using local embedding model to save API costs
embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

# Connect to stand-alone ChromaDB server
import chromadb
vector_db = Chroma(
    client=chromadb.HttpClient(host=settings.CHROMA_SERVER_HOST, port=settings.CHROMA_SERVER_HTTP_PORT),
    embedding_function=embeddings,
    collection_name="challenges"
)

# --- Models ---
class HintRequest(BaseModel):
    user_code: str
    challenge_slug: str
    language: str = "python"
    hint_level: int = 1  # 1: Vague, 2: Moderate, 3: Specific
    user_xp: int = 0

# --- Routes ---

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/big-bang")
async def trigger_big_bang(
    background_tasks: BackgroundTasks, 
    levels: int = 5, 
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")
):
    """
    Triggers the autonomous curriculum generation in the background.
    """
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    background_tasks.add_task(run_big_bang, levels)
    return {"message": f"Big Bang started for {levels} levels. Check AI logs for progress."}

@app.post("/generate-level")
async def generate_single_level(
    background_tasks: BackgroundTasks, 
    level: int, 
    user_id: Optional[int] = None, 
    background: bool = True, 
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")
):
    """
    Generates a specific single level in the background.
    """
    if x_internal_api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")

    async def _run_single(lvl, uid):
        from auto_generator import AutoGenerator
        
        logger.info(f"Generating Single Level {lvl} for User {uid}...")
        try:
            generator = AutoGenerator()
            # AWAIT the async generator
            challenge_json = await generator.generate_level(lvl, user_id=uid)
            
            headers = {
                "X-Internal-API-Key": settings.INTERNAL_API_KEY,
                "Content-Type": "application/json"
            }
            url = f"{settings.CORE_SERVICE_URL}/api/challenges/"
            challenge_json["order"] = lvl
            if uid:
                challenge_json["created_for_user_id"] = uid
            
            # Use Async Client
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=challenge_json, headers=headers)
                if response.status_code in [200, 201]:
                    logger.info(f"Level {lvl} generated and saved successfully for user {uid}.")
                    return True
                else:
                    logger.error(f"Failed to save Level {lvl}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error generating single level {lvl}: {e}")
            return False

    if background:
        background_tasks.add_task(_run_single, level, user_id)
        return {"message": f"Generation started for level {level}"}
    else:
        # Synchronous execution
        success = await _run_single(level, user_id)
        if success:
             return {"message": f"Level {level} generated successfully"}
        else:
             raise HTTPException(status_code=500, detail="Failed to generate level")

@app.post("/hints")
async def generate_hint(
    request: HintRequest, 
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key")
):
    logger.info(f"Received hint request for challenge: {request.challenge_slug}")

    if not settings.INTERNAL_API_KEY:
         logger.warning("Internal API Key not configured, skipping auth check (INSECURE)")
    elif x_internal_api_key != settings.INTERNAL_API_KEY:
        logger.warning(f"Unauthorized hint request. Key: {x_internal_api_key}")
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    if not settings.GROQ_API_KEY:
        logger.error("No LLM API Keys configured")
        raise HTTPException(status_code=500, detail="LLM API Key not configured")

    # 1. Fetch Challenge Context from Core Service
    headers = {"X-Internal-API-Key": settings.INTERNAL_API_KEY}
    try:
        url = f"{settings.CORE_SERVICE_URL}/api/challenges/{request.challenge_slug}/context/"
        logger.info(f"Fetching context from: {url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                 logger.error(f"Core service error: {response.status_code} - {response.text}")
                 raise HTTPException(status_code=response.status_code, detail=f"Core service returned {response.status_code}")
            
            context_data = response.json()
        logger.info("Context fetched successfully")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to Core Service: {e}")
        raise HTTPException(status_code=503, detail="Core service unavailable")

    # 2. Extract Data
    description = context_data.get("description", "")
    test_code = context_data.get("test_code", "")
    
    # 3. RAG: Search for similar challenges
    # Chroma/LangChain vectorstore operations are currently often synchronous or wrapped.
    # We will assume they are fast enough for now or run them in a thread if needed.
    # ideally: await vector_db.asimilarity_search(...)
    logger.info("Performing similarity search for RAG...")
    similar_docs = []
    try:
        query = f"Challenge: {description}\nUser Code: {request.user_code}"
        # using standard sync method for now as chroma python client is sync-heavy
        # wrapping in loop.run_in_executor might be better but let's keep it simple for this pass
        results = vector_db.similarity_search(query, k=2)
        similar_docs = [doc.page_content for doc in results if doc.metadata.get("slug") != request.challenge_slug]
    except Exception as e:
        logger.warning(f"RAG Search failed: {e}. Proceeding without extra context.")

    # 4. Construct Prompt
    rag_context = "\n\n".join(similar_docs) if similar_docs else "No similar patterns found."
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", HINT_GENERATION_SYSTEM_PROMPT),
        ("user", HINT_GENERATION_USER_TEMPLATE)
    ])

    # 5. Call LLM
    try:
        logger.info(f"Initializing LLM via Factory (Provider: {settings.LLM_PROVIDER})")
        from llm_factory import LLMFactory
        
        # Try primary provider
        try:
            llm = LLMFactory.get_llm()
            chain = prompt | llm | StrOutputParser()
            hint = await chain.ainvoke({
                "description": description,
                "test_code": test_code,
                "user_code": request.user_code,
                "hint_level": request.hint_level,
                "user_xp": request.user_xp,
                "rag_context": rag_context
            })
        except Exception as e:
            logger.warning(f"Primary LLM failed: {e}. Attempting fallback...")
            llm = LLMFactory.get_fallback_llm()
            chain = prompt | llm | StrOutputParser()
            hint = await chain.ainvoke({
                "description": description,
                "test_code": test_code,
                "user_code": request.user_code,
                "hint_level": request.hint_level,
                "user_xp": request.user_xp,
                "rag_context": rag_context
            })
            
        logger.info("Hint generated successfully")
        return {"hint": hint}
    except Exception as e:
         logger.error(f"LLM Error (All providers failed): {e}", exc_info=True)
         raise HTTPException(status_code=500, detail="Error generating hint")
