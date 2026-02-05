import json
import logging
import asyncio
import re
import uuid
from typing import List

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from curriculum import get_skill_blueprint
from sandbox import verify_challenge
from prompts import LEVEL_GENERATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

from llm_factory import LLMFactory

# --- Define Output Schema ---
class ChallengeSchema(BaseModel):
    title: str = Field(description="Title of the challenge")
    description: str = Field(description="Detailed markdown description of the problem")
    initial_code: str = Field(description="Starter code for the user", default="# Write your code here\n")
    test_code: str = Field(description="Pytest compatible test code to verify the solution")
    reference_solution: str = Field(description="A working solution that passes the tests")
    hint: str = Field(description="A helpful hint for the user")
    slug: str = Field(description="A unique URL-safe identifier for the challenge")


def validate_challenge_quality(challenge_data: dict, difficulty: str) -> tuple[bool, str]:
    """
    Validates that the generated challenge meets beginner-friendly quality standards.
    Returns (is_valid, error_message).
    """
    # Word count limits by difficulty
    word_limits = {
        "Entry": 100,
        "Basic": 120,
        "Intermediate": 180,
        "Advanced": 250
    }
    
    description = challenge_data.get("description", "")
    word_count = len(description.split())
    max_words = word_limits.get(difficulty, 200)
    
    if word_count > max_words:
        return False, f"Description too long: {word_count} words (max {max_words} for {difficulty})"
    
    # Check initial_code is minimal (no long comments or hints)
    initial_code = challenge_data.get("initial_code", "")
    if len(initial_code.split("\n")) > 5:
        return False, "Initial code should be minimal (max 5 lines)"
    
    # Check test_code has friendly assertions
    test_code = challenge_data.get("test_code", "")
    if "assert" in test_code and "," not in test_code.split("assert")[1].split("\n")[0]:
        # Assertion without error message
        logger.warning("Test code may lack friendly error messages")
    
    # Check for required format elements in description
    if difficulty in ["Entry", "Basic"]:
        if "**Task:**" not in description and "Task:" not in description:
            logger.warning("Description missing Task section")
    
    return True, ""


def extract_json_from_response(raw_response: str) -> str:
    cleaned_response = raw_response.strip()
    # Remove markdown code block markers if present
    if "```json" in cleaned_response:
        cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned_response:
        cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
    
    # Fallback regex if still needed (e.g. text before/after JSON)
    match = re.search(r"\{.*\}", cleaned_response, re.DOTALL)
    if match:
        cleaned_response = match.group(0)
    return cleaned_response

class AutoGenerator:
    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=ChallengeSchema)

    async def generate_level(self, level_number: int, retry_count=0, user_id: int = None):
        blueprint = get_skill_blueprint(level_number)
        
        # Inject Format Instructions into the Prompt
        format_instructions = self.parser.get_format_instructions()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", LEVEL_GENERATION_SYSTEM_PROMPT + "\n\n{format_instructions}"),
            ("human", "Generate challenge for Level {level} using the blueprint.\nTopic: {topic}\nConcepts: {concepts}\nDifficulty: {difficulty}")
        ])
        
        # Generation Logic
        challenge_data: ChallengeSchema = None
        
        try:
            # 1. Try Primary LLM
            try:
                llm = LLMFactory.get_llm()
                # Chain: Prompt -> LLM -> StrOutputParser (to get raw text first)
                chain = prompt | llm | StrOutputParser()
                
                raw_response = await chain.ainvoke({
                    "level": level_number,
                    "topic": blueprint["topic"],
                    "concepts": ", ".join(blueprint["concepts"]),
                    "difficulty": blueprint["difficulty"],
                    "format_instructions": format_instructions
                })

                cleaned_response = extract_json_from_response(raw_response)
                # Parse JSON manually
                json_data = json.loads(cleaned_response)
                challenge_data = ChallengeSchema(**json_data)
            except Exception as e:
                logger.warning(f"Primary LLM failed: {e}. Attempting fallback...")
                # 2. Try Fallback LLM (Same logic)
                llm = LLMFactory.get_fallback_llm()
                # Chain: Prompt -> LLM -> StrOutputParser
                chain = prompt | llm | StrOutputParser()
                
                raw_response = await chain.ainvoke({
                    "level": level_number,
                    "topic": blueprint["topic"],
                    "concepts": ", ".join(blueprint["concepts"]),
                    "difficulty": blueprint["difficulty"],
                    "format_instructions": format_instructions
                })
                
                cleaned_response = extract_json_from_response(raw_response)
                json_data = json.loads(cleaned_response)
                challenge_data = ChallengeSchema(**json_data)

            if not challenge_data:
                raise Exception("Failed to generate valid challenge data.")

            # Convert Pydantic model to Dict for further processing
            data_dict = challenge_data.model_dump()

            # --- QUALITY VALIDATION ---
            is_valid, validation_error = validate_challenge_quality(data_dict, blueprint["difficulty"])
            if not is_valid:
                logger.warning(f"Quality validation failed: {validation_error}")
                if retry_count < 3:
                    logger.info(f"Retrying Level {level_number} due to quality issues...")
                    return await self.generate_level(level_number, retry_count + 1, user_id)
                else:
                    logger.warning("Quality validation failed but proceeding after max retries")

            # --- ENTROPY & NAMESPACING ---
            short_id = str(uuid.uuid4())[:8]
            raw_slug = data_dict.get("slug", f"lvl-{level_number}")
            # Ensure slug is clean
            raw_slug = re.sub(r'[^a-zA-Z0-9-]', '', raw_slug.lower())
            
            if user_id:
                data_dict["slug"] = f"{raw_slug}-u{user_id}-{short_id}"
            else:
                data_dict["slug"] = f"{raw_slug}-{short_id}"

            # --- VERIFICATION ---
            logger.info(f"Validating Level {level_number} for User {user_id}...")
            verification = await verify_challenge(
                data_dict["reference_solution"], 
                data_dict["test_code"]
            )
            
            is_ok = verification.get("passed", False)
            error = verification.get("error", "")
            
            if is_ok:
                logger.info(f"Level {level_number} VERIFIED.")
                return data_dict
            elif "Sandbox not ready" in error:
                 logger.warning(f"Sandbox Bypass: {error}")
                 return data_dict
            else:
                logger.warning(f"Verification FAILED: {error}")
                if retry_count < 3:
                    logger.info(f"Retrying Level {level_number} (Attempt {retry_count + 1})...")
                    return await self.generate_level(level_number, retry_count + 1, user_id)
                else:
                    raise Exception(f"Failed after {retry_count} retries.")

        except Exception as e:
            logger.error(f"Error generating Level {level_number}: {e}")
            if retry_count < 3:
                 return await self.generate_level(level_number, retry_count + 1, user_id)
            raise

if __name__ == "__main__":
    from dotenv import load_dotenv
    from dotenv import load_dotenv
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    gen = AutoGenerator()
    data = asyncio.run(gen.generate_level(1))
    print(json.dumps(data, indent=2))
