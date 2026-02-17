from langchain_core.prompts import ChatPromptTemplate

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


CODE_REVIEW_SYSTEM_PROMPT = """You are a senior Python reviewer for coding challenges.
Return concise, practical feedback in markdown with exactly these sections:
1) Findings
2) Edge Cases
3) Complexity
4) Refactor Suggestion

Rules:
- Be technical and direct.
- Do not include pleasantries.
- Do not provide full final solution unless absolutely necessary.
- Focus on correctness first, then complexity/readability.
"""

CODE_REVIEW_USER_TEMPLATE = """
Challenge: {challenge_title}
Description: {challenge_description}
Starter Code:
```python
{initial_code}
```
User Code:
```python
{user_code}
```
Tests:
```python
{test_code}
```
Similar Challenges Context: {rag_context}

Generate a code review following the required sections.
"""

