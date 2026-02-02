import os
import requests
from dotenv import load_dotenv
load_dotenv()
import logging
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
import chromadb

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
# Force localhost for host-side indexing since docker 'core' dns is not available here
CORE_SERVICE_URL = "http://localhost"
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
CHROMA_PATH = "chroma_db"

def index_challenges():
    logger.info("Starting challenge indexing...")
    logger.info(f"Using key: {INTERNAL_API_KEY}")
    
    # 1. Fetch Challenges from Core
    headers = {"X-Internal-API-Key": INTERNAL_API_KEY}
    try:
        url = f"{CORE_SERVICE_URL}/api/challenges/internal-list/"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            logger.error(f"Failed to fetch challenges: {response.status_code}")
            return
        
        challenges = response.json()
        logger.info(f"Fetched {len(challenges)} challenges")
    except Exception as e:
        logger.error(f"Error fetching challenges: {e}")
        return

    # 2. Prepare Data
    documents = []
    metadatas = []
    ids = []
    
    for chall in challenges:
        slug = chall.get("slug")
        content = f"Title: {chall.get('title')}\nDescription: {chall.get('description')}\nTest Code: {chall.get('test_code')}"
        documents.append(content)
        metadatas.append({"slug": slug, "title": chall.get("title")})
        ids.append(slug)

    # 3. Initialize Embeddings and Vector DB
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vector_db = Chroma.from_texts(
        texts=documents,
        embedding=embeddings,
        metadatas=metadatas,
        ids=ids,
        persist_directory=CHROMA_PATH
    )
    
    logger.info(f"Indexing complete. {len(documents)} documents indexed.")

if __name__ == "__main__":
    index_challenges()
