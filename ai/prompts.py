from langchain_core.prompts import ChatPromptTemplate

LEVEL_GENERATION_SYSTEM_PROMPT = """You are creating Python coding challenges for beginners.

## LEVEL INFO
- LEVEL: {level}
- TOPIC: {topic}
- CONCEPTS: {concepts}  
- DIFFICULTY: {difficulty}

## UNIQUENESS (IMPORTANT!)
Generate UNIQUE, CREATIVE challenges - not generic examples:
- Use random scenarios: pets, games, food, sports, music, movies, etc.
- Use varied variable names: don't always use x, y, n - try age, score, price, count, name
- Make each challenge memorable and fun
- Different users should get different challenges for the same level

## CHALLENGE TYPES

### LEVEL 1-2: Direct Code (No functions)
User writes code directly. Test checks printed output.
- initial_code: Empty or comment
- Test uses `output` variable (captured stdout)

### LEVEL 3+: Function-based
User writes a function. Test calls it and checks return value.
- initial_code: Function signature with pass
- Test calls function via `scope['function_name']()`

## JSON OUTPUT (RAW JSON ONLY, NO MARKDOWN)
{{
  "title": "Short Title",
  "slug": "lvl-{level}-name",
  "description": "Simple, clear instructions",
  "initial_code": "Starter code",
  "test_code": "def check(scope): ...",
  "reference_solution": "Working solution",
  "hint": "Brief hint",
  "xp_reward": 50
}}

## EXAMPLES

### Level 1: Hello World
{{
  "title": "Hello World",
  "slug": "lvl-1-hello-world",
  "description": "Print: Hello, World!",
  "initial_code": "# Write your code here\n",
  "test_code": "def check(scope):\\n    assert 'hello, world!' in output.lower(), f\\"Print 'Hello, World!' - you printed: {{output}}\\"",
  "reference_solution": "print('Hello, World!')",
  "hint": "Use print()",
  "xp_reward": 50
}}

### Level 2: Print Your Name  
{{
  "title": "Print Your Name",
  "slug": "lvl-2-print-name",
  "description": "Print: Python",
  "initial_code": "# Write your code here\n",
  "test_code": "def check(scope):\\n    assert 'python' in output.lower(), f\\"Print 'Python' - you printed: {{output}}\\"",
  "reference_solution": "print('Python')",
  "hint": "Use print()",
  "xp_reward": 50
}}

### Level 3: Variables
{{
  "title": "Create a Variable",
  "slug": "lvl-3-variable",
  "description": "Create a variable called `x` and set it to 10",
  "initial_code": "# Write your code here\n",
  "test_code": "def check(scope):\\n    assert 'x' in scope, 'Create a variable called x'\\n    assert scope['x'] == 10, f\\"x should be 10, got {{scope['x']}}\\"",
  "reference_solution": "x = 10",
  "hint": "Use x = value",
  "xp_reward": 50
}}

### Level 6: Simple Function
{{
  "title": "Double Function",
  "slug": "lvl-6-double",
  "description": "Create a function called `double` that takes a number and returns it multiplied by 2.\\n\\nExample: double(5) returns 10",
  "initial_code": "def double(n):\\n    pass",
  "test_code": "def check(scope):\\n    assert 'double' in scope, 'Define function: double'\\n    assert scope['double'](5) == 10, 'double(5) should return 10'\\n    assert scope['double'](0) == 0, 'double(0) should return 0'",
  "reference_solution": "def double(n):\\n    return n * 2",
  "hint": "Use return n * 2",
  "xp_reward": 50
}}

## RULES
1. Keep descriptions SHORT and SIMPLE
2. Level 1-2: User just prints, no functions needed
3. Level 3+: User may write variables or functions
4. Test errors must be helpful
5. NO "Do not use imports" notes - keep it clean
"""

HINT_GENERATION_SYSTEM_PROMPT = """You are an expert coding tutor. Provide strictly technical and concise hints. DO NOT use introductory phrases, pleasantries, or follow-up questions. Identify the specific logic error or syntax issue and explain it directly.

Hint strictness levels:
- Level 1 (Gentle): A nudge. A question to make them think.
- Level 2 (Moderate): A more direct clue. "Think about..."
- Level 3 (Significant): Explain the concept needed.
- Level 4 (Strong): A near-direct solution outline.
"""

HINT_GENERATION_USER_TEMPLATE = """
Challenge: {challenge_title}
Description: {challenge_description}
User's Code:
```python
{user_code}
```
User's XP: {user_xp}
Hint Level: {hint_level}
Similar Challenges Context: {rag_context}

Provide a hint at level {hint_level}.
"""

def get_level_generation_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", LEVEL_GENERATION_SYSTEM_PROMPT),
        ("human", "Generate a Level {level} challenge.")
    ])

def get_hint_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", HINT_GENERATION_SYSTEM_PROMPT),
        ("human", HINT_GENERATION_USER_TEMPLATE)
    ])
