import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import requests
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

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

@app.get("/health")
def health():
    return {"status": "ok"}

import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert coding tutor. Your goal is to provide a helpful hint to a student who is stuck on a coding challenge. "
                   "Do NOT give the direct solution. Analyze their code and the challenge requirements. "
                   "Identify the error or misconception. Provide a hint that guides them towards the solution. "
                   "Be encouraging and concise."),
        ("user", "Challenge Description:\n{description}\n\n"
                 "Test Code:\n{test_code}\n\n"
                 "Student's Code:\n{user_code}\n\n"
                 "Provide a progressive hint (start with a nudge):")
    ])

    # 3. Call LLM
    try:
        logger.info(f"Initializing LLM with model: {MODEL_NAME} and base_url: {OPENAI_API_BASE}")
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
            "user_code": request.user_code
        })
        logger.info("Hint generated successfully")
    except Exception as e:
         logger.error(f"LLM Error: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail="Error generating hint")

    return {"hint": hint}
