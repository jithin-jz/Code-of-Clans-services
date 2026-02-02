import os
import json
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from curriculum import get_skill_blueprint
from sandbox import verify_challenge

logger = logging.getLogger(__name__)

class AutoGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("MODEL_NAME", "llama-3.3-70b-versatile"),
            openai_api_key=os.getenv("GROQ_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE")
        )

    def generate_level(self, level_number: int, retry_count=0, user_id: int = None):
        blueprint = get_skill_blueprint(level_number)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Coding Mentor for absolute beginners.
Your task is to generate a fun, encouraging, and clear Python coding challenge for Level {level}.

CRITICAL REQUIREMENTS:
1. FOCUS: {topic}
2. CONCEPTS: {concepts}
3. DIFFICULTY: {difficulty}
4. FORMAT: You MUST output ONLY valid JSON. No conversational text.
5. SCHEMA:
{{
  "title": "Concise Technical Title",
  "slug": "lvl-{level}-short-name",
  "description": "Clear and direct instructions. No stories or metaphors. Just state what needs to be done.",
  "initial_code": "def function_name():\\n    # Your code here\\n    pass",
  "test_code": "Pytest-style assertions in check(scope) format.",
  "reference_solution": "Simple, clean solution.",
  "xp_reward": 50
}}

RULES:
- Level 1 MUST be a simple "Hello World" or basic print task.
- Use clear, direct English. No fluff.
- If the topic is "Variables", just ask to assign a value.
- If the topic is "Loops", ask to iterate and print/sum.
- Focus on the technical skill only.

TESTING INSTRUCTION (CRITICAL):
- The `test_code` MUST define a function named `check(scope)`.
- `scope` is a dictionary containing the user's defined variables and functions.
- DO NOT just write asserts at the top level. Wrap them in `check(scope)`.
- To access user variables: `val = scope.get('var_name')`.
- To access user functions: `func = scope.get('func_name')`.
- Example for Variables:
  ```python
  def check(scope):
      assert 'my_var' in scope, "Did you define 'my_var'?"
      assert scope['my_var'] == 10, "my_var should be 10"
  ```
- Example for Functions:
  ```python
  def check(scope):
      assert 'solution' in scope, "Did you define 'solution'?"
      func = scope['solution']
      assert func(1, 2) == 3
  ```
- Example for Prints (Stdout):
  ```python
  import sys
  from io import StringIO
  def check(scope):
      # We cannot easily capture stdout this way in the runner unless we mock it BEFORE running user code.
      # Ideally, avoid "print" challenges if possible, or assume the runner captures it in a global way.
      # BUT, if you must check print, just check if the function exists for now or use return values.
      pass
  ```
"""),
            ("human", "Generate challenge for Level {level} using the blueprint.")
        ])

        chain = prompt | self.llm
        
        try:
            response = chain.invoke({
                "level": level_number,
                "topic": blueprint["topic"],
                "concepts": ", ".join(blueprint["concepts"]),
                "difficulty": blueprint["difficulty"]
            })

            # Clean the output (remove markdown code blocks if present)
            content = response.content.replace("```json", "").replace("```", "").strip()
            challenge_data = json.loads(content)

            # --- NAMESPACE THE SLUG ---
            # Append user ID and a short random string to ensure total uniqueness
            import uuid
            import re
            short_id = str(uuid.uuid4())[:8]
            raw_slug = challenge_data.get("slug", f"lvl-{level_number}")
            
            # Clean raw_slug (lowercase, alphanumeric, hyphens)
            raw_slug = re.sub(r'[^a-zA-Z0-9-]', '', raw_slug.lower())
            
            if user_id:
                challenge_data["slug"] = f"{raw_slug}-u{user_id}-{short_id}"
            else:
                challenge_data["slug"] = f"{raw_slug}-{short_id}"

            # --- DOUBLE-LOOP VALIDATION ---
            logger.info(f"Validating Level {level_number} for User {user_id}...")
            is_ok, error = verify_challenge(
                challenge_data["reference_solution"], 
                challenge_data["test_code"]
            )

            if is_ok:
                logger.info(f"Level {level_number} VERIFIED.")
                return challenge_data
            else:
                logger.warning(f"Verification FAILED for Level {level_number}: {error}")
                if retry_count < 3:
                    logger.info(f"Retrying Level {level_number} (Attempt {retry_count + 2})...")
                    return self.generate_level(level_number, retry_count + 1, user_id)
                else:
                    raise Exception(f"Failed to generate a valid level after {retry_count} retries.")

        except Exception as e:
            logger.error(f"Error generating Level {level_number}: {str(e)}")
            raise

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    gen = AutoGenerator()
    data = gen.generate_level(1)
    print(json.dumps(data, indent=2))
