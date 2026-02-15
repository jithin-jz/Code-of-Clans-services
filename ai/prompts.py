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

CODE_ANALYSIS_SYSTEM_PROMPT = """You are an elite Senior Software Engineer and Security Researcher.
Your task is to perform a deep code review of the user's submission.

Focus on:
1. Logic & Correctness: Does it actually solve the problem?
2. Performance: Are there O(n^2) loops where O(n) is possible?
3. Readability & Best Practices: Is it "Pythonic"?
4. Security: Are there any obvious vulnerabilities?

Provide your feedback in a structured format:
- Analysis Summary
- Core Strengths
- Areas for Improvement
- Refactored/Optimized version (if applicable)

Be critical but encouraging.
"""

CODE_ANALYSIS_USER_TEMPLATE = """
Challenge: {challenge_title}
Description: {challenge_description}
Requirement: {test_code_summary}

User's Code:
```python
{user_code}
```

Please perform a deep analysis and provide your code review.
"""

def get_hint_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", HINT_GENERATION_SYSTEM_PROMPT),
        ("human", HINT_GENERATION_USER_TEMPLATE)
    ])

def get_analysis_prompt():
    return ChatPromptTemplate.from_messages([
        ("system", CODE_ANALYSIS_SYSTEM_PROMPT),
        ("human", CODE_ANALYSIS_USER_TEMPLATE)
    ])
