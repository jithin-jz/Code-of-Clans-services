# Professional Skill Matrix for Automated Curriculum Generation
# Designed for absolute beginners learning Python through practice

SKILL_MATRIX = {
    # Entry Levels (1-5): Ultra simple, ONE concept per level
    1: {"topic": "Hello World", "concepts": ["print()"], "difficulty": "Entry"},
    2: {"topic": "Printing Text", "concepts": ["print()", "strings"], "difficulty": "Entry"},
    3: {"topic": "Variables", "concepts": ["variables", "assignment"], "difficulty": "Entry"},
    4: {"topic": "Numbers & Math", "concepts": ["integers", "addition", "subtraction"], "difficulty": "Entry"},
    5: {"topic": "User Input", "concepts": ["input()", "type casting"], "difficulty": "Entry"},
    
    # Basic Levels (6-10): Introduce functions and conditionals
    6: {"topic": "Simple Functions", "concepts": ["def", "return"], "difficulty": "Basic"},
    7: {"topic": "Function Parameters", "concepts": ["parameters", "arguments"], "difficulty": "Basic"},
    8: {"topic": "Boolean Logic", "concepts": ["True", "False", "comparison"], "difficulty": "Basic"},
    9: {"topic": "If Statements", "concepts": ["if", "else"], "difficulty": "Basic"},
    10: {"topic": "Multiple Conditions", "concepts": ["elif", "and", "or"], "difficulty": "Basic"},
    
    # Intermediate Levels (11-15): Loops and data structures
    11: {"topic": "While Loops", "concepts": ["while", "loop condition"], "difficulty": "Intermediate"},
    12: {"topic": "For Loops", "concepts": ["for", "range()"], "difficulty": "Intermediate"},
    13: {"topic": "Lists Basics", "concepts": ["list creation", "indexing"], "difficulty": "Intermediate"},
    14: {"topic": "List Operations", "concepts": ["append", "remove", "len()"], "difficulty": "Intermediate"},
    15: {"topic": "String Methods", "concepts": ["upper()", "lower()", "split()"], "difficulty": "Intermediate"},
    
    # Advanced Levels (16-20): Complex structures and OOP intro
    16: {"topic": "Nested Loops", "concepts": ["loops within loops"], "difficulty": "Advanced"},
    17: {"topic": "Dictionaries", "concepts": ["key-value pairs", "dict operations"], "difficulty": "Advanced"},
    18: {"topic": "List Comprehensions", "concepts": ["list comprehension syntax"], "difficulty": "Advanced"},
    19: {"topic": "Classes Intro", "concepts": ["class", "__init__", "self"], "difficulty": "Advanced"},
    20: {"topic": "Class Methods", "concepts": ["methods", "attributes"], "difficulty": "Advanced"},
    
    # Expert Levels (21+): Generated dynamically
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
