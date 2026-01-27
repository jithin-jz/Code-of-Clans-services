from django.core.management.base import BaseCommand
from challenges.models import Challenge
import textwrap

class Command(BaseCommand):
    help = 'Seeds a comprehensive 30-level Python curriculum.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Python Curriculum...')

        # 1. Clean Slate
        self.stdout.write('Wiping existing challenges...')
        Challenge.objects.all().delete()

        # 2. Define Curriculum Data
        # Format: (Order, Title, Desc, InitialCode, TestCode, XP)
        challenges_data = [
            # --- 1. BASICS (1-5) ---
            (1, "Hello World", "Print 'Hello, World!' to the console.", 
             "def solution():\n    # Write your code here\n    pass", 
             "import sys\nfrom io import StringIO\ndef check(sol):\n    out = StringIO()\n    sys.stdout = out\n    sol()\n    sys.stdout = sys.__stdout__\n    assert out.getvalue().strip() == 'Hello, World!'", 10),
            
            (2, "Basic Arithmetic", "Return the sum of a and b.", 
             "def add(a, b):\n    return 0", 
             "def check(scope):\n    assert scope['add'](5, 7) == 12\n    assert scope['add'](-1, 1) == 0", 10),
             
            (3, "Variables", "Assign the value 10 to variable 'x' and return it.", 
             "def get_x():\n    # x = ...\n    return 0", 
             "def check(scope):\n    assert scope['get_x']() == 10", 15),

            (4, "Strings", "Return the string 'Python' in uppercase.", 
             "def shout():\n    s = 'Python'\n    return s", 
             "def check(scope):\n    assert scope['shout']() == 'PYTHON'", 15),

            (5, "String Slicing", "Return the first 3 characters of the string s.",
             "def first_three(s):\n    return s",
             "def check(scope):\n    assert scope['first_three']('abcdef') == 'abc'", 20),

            # --- 2. LOGIC & FLOW (6-10) ---
            (6, "If Else", "Return 'Positive' if n > 0, else 'Non-positive'.",
             "def check_sign(n):\n    pass",
             "def check(scope):\n    f = scope['check_sign']\n    assert f(5) == 'Positive'\n    assert f(-2) == 'Non-positive'", 20),

            (7, "Multiple Conditions", "Return 'A' for n>=90, 'B' for n>=80, else 'C'.",
             "def grade(n):\n    pass",
             "def check(scope):\n    f = scope['grade']\n    assert f(95) == 'A'\n    assert f(85) == 'B'\n    assert f(70) == 'C'", 25),

            (8, "For Loops", "Return the sum of numbers from 0 to n.",
             "def sum_up_to(n):\n    pass",
             "def check(scope):\n    f = scope['sum_up_to']\n    assert f(3) == 6\n    assert f(5) == 15", 25),

            (9, "While Loops", "Keep doubling x while it is less than 100. Return final x.",
             "def double_until_100(x):\n    pass",
             "def check(scope):\n    f = scope['double_until_100']\n    assert f(10) == 160\n    assert f(50) == 100", 30),

            (10, "Modulo Operator", "Return True if n is even, False otherwise.",
             "def is_even(n):\n    pass",
             "def check(scope):\n    f = scope['is_even']\n    assert f(4) == True\n    assert f(3) == False", 30),

            # --- 3. DATA STRUCTURES I (11-15) ---
            (11, "Lists", "Return a list containing numbers 1, 2, 3.",
             "def get_list():\n    pass",
             "def check(scope):\n    assert scope['get_list']() == [1, 2, 3]", 35),

            (12, "List Methods", "Append 'World' to the list ['Hello'] and return it.",
             "def add_world(lst):\n    # lst is ['Hello']\n    pass",
             "def check(scope):\n    assert scope['add_world'](['Hello']) == ['Hello', 'World']", 35),

            (13, "Dictionaries", "Create dict with key 'name' and value 'Alice'.",
             "def create_dict():\n    pass",
             "def check(scope):\n    assert scope['create_dict']() == {'name': 'Alice'}", 40),

            (14, "Dict Access", "Return the value of 'age' from the dictionary.",
             "def get_age(person):\n    pass",
             "def check(scope):\n    assert scope['get_age']({'age': 25}) == 25", 40),

            (15, "Sets", "Return unique elements from list [1, 1, 2].",
             "def unique_elements(lst):\n    pass",
             "def check(scope):\n    assert scope['unique_elements']([1, 1, 2]) == {1, 2}", 45),

            # --- 4. DATA STRUCTURES II (16-20) ---
            (16, "Tuples", "Swap elements in a 2-element tuple.",
             "def swap_tuple(t):\n    return (t[1], t[0])",
             "def check(scope):\n    assert scope['swap_tuple']((1, 2)) == (2, 1)", 45),
            
            (17, "String Split", "Split 'a,b,c' by comma into a list.",
             "def split_csv(s):\n    pass",
             "def check(scope):\n    assert scope['split_csv']('a,b,c') == ['a', 'b', 'c']", 50),

            (18, "String Join", "Join list ['a', 'b', 'c'] with dashes.",
             "def join_dashes(lst):\n    pass",
             "def check(scope):\n    assert scope['join_dashes'](['a', 'b', 'c']) == 'a-b-c'", 50),

            (19, "Range Steps", "Return list of even numbers from 0 to 10 using range().",
             "def evens_range():\n    pass",
             "def check(scope):\n    assert scope['evens_range']() == [0, 2, 4, 6, 8, 10]", 55),

            (20, "Nested Loops", "Return a flattening of [[1,2], [3,4]] -> [1,2,3,4]",
             "def flatten(matrix):\n    pass",
             "def check(scope):\n    assert scope['flatten']([[1,2],[3,4]]) == [1,2,3,4]", 60),

            # --- 5. FUNCTIONS (21-25) ---
            (21, "Default Arguments", "Function 'greet(name)'. Default name='Guest'. Return 'Hi {name}'",
             "def greet(name='Guest'):\n    pass",
             "def check(scope):\n    f = scope['greet']\n    assert f() == 'Hi Guest'\n    assert f('Bob') == 'Hi Bob'", 60),

            (22, "Arbitrary Args", "Function that returns sum of all arguments (*args).",
             "def sum_all(*args):\n    pass",
             "def check(scope):\n    assert scope['sum_all'](1, 2, 3) == 6", 65),

            (23, "Lambda Functions", "Use lambda to return the cube of a number.",
             "cube = lambda x: x",
             "def check(scope):\n    assert scope['cube'](3) == 27", 65),

            (24, "Map Function", "Use map to double values in a list.",
             "def double_all(lst):\n    pass",
             "def check(scope):\n    assert list(scope['double_all']([1, 2])) == [2, 4]", 70),

            (25, "Filter Function", "Use filter to keep only words longer than 3 chars.",
             "def filter_long_words(words):\n    pass",
             "def check(scope):\n    assert list(scope['filter_long_words'](['hi', 'hello'])) == ['hello']", 75),

            # --- 6. OBJECT ORIENTED PROGRAMMING (26-30) ---
            (26, "Classes & Objects", "Define class Dog with method bark() returning 'Woof'",
             "class Dog:\n    pass",
             "def check(scope):\n    assert scope['Dog']().bark() == 'Woof'", 75),

            (27, "Constructor __init__", "Person class stores name and age.",
             "class Person:\n    pass",
             "def check(scope):\n    p = scope['Person']('Alice', 25)\n    assert p.name == 'Alice' and p.age == 25", 80),

            (28, "Inheritance", "Student inherits from Person. Student has student_id.",
             "class Person:\n    def __init__(self, name): self.name = name\nclass Student(Person):\n    pass",
             "def check(scope):\n    s = scope['Student']('Bob', 123)\n    assert s.name == 'Bob' and s.student_id == 123", 85),

            (29, "Polymorphism", "Override __str__ to return 'Instance of MyClass'",
             "class MyClass:\n    pass",
             "def check(scope):\n    assert str(scope['MyClass']()) == 'Instance of MyClass'", 90),

            (30, "Static Methods", "Add @staticmethod 'add(a,b)' to Calculator class.",
             "class Calculator:\n    pass",
             "def check(scope):\n    assert scope['Calculator'].add(2, 3) == 5", 95),

            # --- 7. STANDARD LIBRARY (31-35) ---
            (31, "Math Module", "Import math and return square root of n.",
             "import math\ndef get_sqrt(n):\n    pass",
             "def check(scope):\n    assert scope['get_sqrt'](16) == 4", 100),

            (32, "Random Module", "Return a random number between 1 and 10 using random.randint.",
             "import random\ndef roll_dice():\n    pass",
             "import random\ndef check(scope):\n    random.seed(1)\n    res = scope['roll_dice']()\n    assert 1 <= res <= 10", 100),

            (33, "Date & Time", "Return the current year using datetime.",
             "from datetime import datetime\ndef current_year():\n    pass",
             "import datetime\ndef check(scope):\n    assert scope['current_year']() == datetime.datetime.now().year", 105),

            (34, "JSON Parsing", "Parse JSON string '{\"a\":1}' and return value of 'a'.",
             "import json\ndef parse_a(json_str):\n    pass",
             "def check(scope):\n    assert scope['parse_a']('{\"a\":1}') == 1", 105),

            (35, "Regular Expressions", "Find all digits in string 'a1b2' using re.findall.",
             "import re\ndef extract_digits(s):\n    pass",
             "def check(scope):\n    assert scope['extract_digits']('a1b2') == ['1', '2']", 110),

            # --- 8. ADVANCED LOGIC (36-40) ---
            (36, "List Comprehension", "Create list of squares for evens only from 0-10.",
             "def even_squares():\n    pass",
             "def check(scope):\n    assert scope['even_squares']() == [0, 4, 16, 36, 64, 100]", 115),

            (37, "Generators", "Create a generator that yields 'A', then 'B', then 'C'.",
             "def abc_gen():\n    pass",
             "def check(scope):\n    assert list(scope['abc_gen']()) == ['A', 'B', 'C']", 120),

            (38, "Decorators", "Write a decorator that multiplies result by 2.",
             "def double_result(func):\n    pass",
             "def check(scope):\n    dec = scope['double_result']\n    @dec\n    def f(): return 5\n    assert f() == 10", 125),

            (39, "Error Handling", "Catch IndexError when accessing list out of bounds.",
             "def safe_get(lst, idx):\n    pass",
             "def check(scope):\n    assert scope['safe_get']([1], 5) is None", 130),

            (40, "Context Managers", "Use 'with open' mock logic (simulated). Return 'Closed'.",
             "# This implies understanding structure, though we can't test file IO easily safely.\n# Just return 'Closed'\ndef context_demo():\n    return 'Closed'",
             "def check(scope):\n    assert scope['context_demo']() == 'Closed'", 130),

            # --- 9. ALGORITHMS (41-45) ---
            (41, "Sum of Digits", "Calculate sum of digits of integer n.",
             "def sum_digits(n):\n    pass",
             "def check(scope):\n    assert scope['sum_digits'](123) == 6", 140),

            (42, "Palindrome Check", "Return True if string is palindrome.",
             "def is_palindrome(s):\n    pass",
             "def check(scope):\n    assert scope['is_palindrome']('aba') == True", 145),

            (43, "Fibonacci", "Return nth Fibonacci number (0,1,1,2...).",
             "def fib(n):\n    pass",
             "def check(scope):\n    assert scope['fib'](5) == 5", 150),

            (44, "Linear Search", "Return index of target in list, or -1.",
             "def search(lst, target):\n    pass",
             "def check(scope):\n    assert scope['search']([10, 20, 30], 20) == 1", 155),

            (45, "Bubble Sort", "Sort list manually (or use sorted, but verify sorting).",
             "def my_sort(lst):\n    pass",
             "def check(scope):\n    assert scope['my_sort']([3, 1, 2]) == [1, 2, 3]", 160),

            # --- 10. EXPERT & FINAL (46-50) ---
            (46, "Anagrams", "Return True if s1 and s2 are anagrams.",
             "def check_anagram(s1, s2):\n    pass",
             "def check(scope):\n    assert scope['check_anagram']('listen', 'silent') == True", 170),

            (47, "Flatten Deep List", "Flatten arbitrary nested list [1, [2, [3]]].",
             "def deep_flatten(lst):\n    pass",
             "def check(scope):\n    assert list(scope['deep_flatten']([1, [2, [3]]])) == [1, 2, 3]", 180),

            (48, "Binary Search", "Implement binary search on sorted list.",
             "def bin_search(arr, x):\n    # Return index or -1\n    pass",
             "def check(scope):\n    assert scope['bin_search']([1, 3, 5, 7], 5) == 2", 190),

            (49, "Prime Sieve", "Return list of primes up to n.",
             "def sieve(n):\n    pass",
             "def check(scope):\n    assert scope['sieve'](10) == [2, 3, 5, 7]", 200),

            (50, "Final Boss: Sudoku Validator", "Check if 9x9 grid is valid (just checking rows for simplicity).",
             "def check_rows_valid(board):\n    pass",
             "def check(scope):\n    r = [1,2,3,4,5,6,7,8,9]\n    assert scope['check_rows_valid']([r, r, r, r, r, r, r, r, r]) == True", 500),
        ]

        # 3. Create Challenges
        for order, title, desc, code, test, xp in challenges_data:
            Challenge.objects.create(
                slug=f"lvl-{order}-{title.lower().replace(' ', '-')}",
                title=title,
                description=desc,
                initial_code=code,
                test_code=test,
                order=order,
                xp_reward=xp,
                time_limit=300
            )

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {len(challenges_data)} levels.'))
