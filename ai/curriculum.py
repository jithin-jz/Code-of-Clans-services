# Professional Skill Matrix for Automated Curriculum Generation

SKILL_MATRIX = {
    1: {"topic": "Output & Strings", "concepts": ["print()", "string literals"], "difficulty": "Entry"},
    2: {"topic": "Variables & Types", "concepts": ["assignment", "integers", "floats"], "difficulty": "Entry"},
    3: {"topic": "Basic Math", "concepts": ["arithmetic operators", "precedence"], "difficulty": "Entry"},
    4: {"topic": "Input Handling", "concepts": ["input()", "type casting"], "difficulty": "Entry"},
    5: {"topic": "Boolean Logic", "concepts": ["comparison operators", "booleans"], "difficulty": "Basic"},
    6: {"topic": "Conditional Branching", "concepts": ["if", "else"], "difficulty": "Basic"},
    7: {"topic": "Multiple Conditions", "concepts": ["elif", "and", "or", "not"], "difficulty": "Basic"},
    8: {"topic": "While Loops", "concepts": ["iteration", "loop condition", "counters"], "difficulty": "Basic"},
    9: {"topic": "Infinite Loops & Break", "concepts": ["break", "while True"], "difficulty": "Basic"},
    10: {"topic": "Introduction to Lists", "concepts": ["list creation", "indexing"], "difficulty": "Intermediate"},
    11: {"topic": "List Operations", "concepts": ["append", "remove", "pop"], "difficulty": "Intermediate"},
    12: {"topic": "For Loops", "concepts": ["iterating over lists", "range()"], "difficulty": "Intermediate"},
    13: {"topic": "String Manipulation", "concepts": ["slicing", "upper/lower", "find"], "difficulty": "Intermediate"},
    14: {"topic": "Nested Loops", "concepts": ["loops within loops", "2D thinking"], "difficulty": "Intermediate"},
    15: {"topic": "Dictionary Basics", "concepts": ["key-value pairs", "lookup"], "difficulty": "Intermediate"},
    # Higher levels will be procedurally derived from these foundations
}

def get_skill_blueprint(level):
    """
    Returns the specific skill requirements for a given level.
    If level > 15, it starts combining previous skills for higher difficulty.
    """
    if level in SKILL_MATRIX:
        return SKILL_MATRIX[level]
    
    # Procedural difficulty for levels 16+
    return {
        "topic": "Advanced Application",
        "concepts": ["Algorithm design", "Combination of basics"],
        "difficulty": "Advanced"
    }
