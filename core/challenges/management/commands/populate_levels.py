from django.core.management.base import BaseCommand
from challenges.models import Challenge
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Populates the database with 25 initial challenges'

    def handle(self, *args, **kwargs):
        self.stdout.write('Populating levels...')
        
        # Define some basic tasks to start with
        tasks = [
            (
                "Print Hello World", 
                "Write a function `solve` that prints 'Hello World'.", 
                "def solve():\n    pass", 
                "import sys\nfrom io import StringIO\n\ndef check():\n    capturedOutput = StringIO()\n    sys.stdout = capturedOutput\n    solve()\n    sys.stdout = sys.__stdout__\n    assert capturedOutput.getvalue().strip() == 'Hello World', 'Output must be Hello World'\n\ncheck()"
            ),
            (
                "Sum of Two Numbers", 
                "Write a function `add(a, b)` that returns the sum of a and b.", 
                "def add(a, b):\n    pass", 
                "assert add(2, 3) == 5\nassert add(-1, 1) == 0\nassert add(0, 0) == 0"
            ),
            (
                "Return True", 
                "Write a function `is_true` that always returns True.", 
                "def is_true():\n    pass", 
                "assert is_true() is True"
            ),
            (
                "Is Even", 
                "Write a function `is_even(n)` that returns True if n is even, else False.", 
                "def is_even(n):\n    pass", 
                "assert is_even(2) is True\nassert is_even(3) is False\nassert is_even(0) is True"
            ),
            (
                "Convert Minutes to Seconds", 
                "Write a function `convert(minutes)` that returns the seconds equivalent.", 
                "def convert(minutes):\n    pass", 
                "assert convert(5) == 300\nassert convert(3) == 180\nassert convert(2) == 120"
            ),
            (
                "Return the First Element", 
                "Write a function `get_first_value(lst)` that returns the first element of a list.", 
                "def get_first_value(lst):\n    pass", 
                "assert get_first_value([1, 2, 3]) == 1\nassert get_first_value([80, 5, 100]) == 80"
            ),
            (
                "Area of a Triangle", 
                "Write a function `tri_area(base, height)` that returns the area of a triangle.", 
                "def tri_area(base, height):\n    pass", 
                "assert tri_area(3, 2) == 3\nassert tri_area(7, 4) == 14\nassert tri_area(10, 10) == 50"
            ),
            (
                "Remainder of Division", 
                "Write a function `remainder(x, y)` that returns the remainder of x divided by y.", 
                "def remainder(x, y):\n    pass", 
                "assert remainder(1, 3) == 1\nassert remainder(3, 4) == 3\nassert remainder(-9, 45) == -9\nassert remainder(5, 5) == 0"
            ),
            (
                "Less Than 100", 
                "Write a function `less_than_100(a, b)` that returns True if the sum of two numbers is less than 100, else False.", 
                "def less_than_100(a, b):\n    pass", 
                "assert less_than_100(22, 15) is True\nassert less_than_100(83, 34) is False\nassert less_than_100(3, 77) is True"
            ),
            (
                "Is Equal", 
                "Write a function `is_equal(num1, num2)` that returns True if num1 is equal to num2, else False.", 
                "def is_equal(num1, num2):\n    pass", 
                "assert is_equal(3, 3) is True\nassert is_equal(1, 5) is False"
            ),
            (
                "Reverse a String", 
                "Write a function `reverse(txt)` that returns the string in reverse order.", 
                "def reverse(txt):\n    pass", 
                "assert reverse('Hello') == 'olleH'\nassert reverse('World') == 'dlroW'\nassert reverse('a') == 'a'"
            ),
            (
                "Check Ending", 
                "Write a function `check_ending(str1, str2)` that returns True if the first string ends with the second string.", 
                "def check_ending(str1, str2):\n    pass", 
                "assert check_ending('abc', 'bc') is True\nassert check_ending('abc', 'd') is False"
            ),
            (
                "Find the Smallest Number", 
                "Write a function `find_smallest_num(lst)` that returns the smallest number in a list.", 
                "def find_smallest_num(lst):\n    pass", 
                "assert find_smallest_num([34, 15, 88, 2]) == 2\nassert find_smallest_num([34, -345, -1, 100]) == -345"
            ),
            (
                "Difference of Max and Min", 
                "Write a function `diff_max_min(lst)` that takes a list of numbers and returns the difference between the largest and smallest numbers.", 
                "def diff_max_min(lst):\n    pass", 
                "assert diff_max_min([10, 4, 1, 4, -10, -50, 32, 21]) == 82\nassert diff_max_min([44, 32, 86, 19]) == 67"
            ),
            (
                "Name Greeting", 
                "Write a function `hello_name(name)` that returns 'Hello {name}!'", 
                "def hello_name(name):\n    pass", 
                "assert hello_name('Gerald') == 'Hello Gerald!'\nassert hello_name('Tiffany') == 'Hello Tiffany!'"
            ),
            (
                "Remove First and Last Character", 
                "Write a function `remove_first_last(txt)` that removes the first and last characters from a string.", 
                "def remove_first_last(txt):\n    pass", 
                "assert remove_first_last('hello') == 'ell'\nassert remove_first_last('benefit') == 'enefi'\nassert remove_first_last('a') == 'a'"
            ),
            (
                "Factorial", 
                "Write a function `factorial(n)` that returns the factorial of a non-negative integer n.", 
                "def factorial(n):\n    pass", 
                "assert factorial(5) == 120\nassert factorial(3) == 6\nassert factorial(0) == 1\nassert factorial(1) == 1"
            ),
            (
                "Palindrome",
                "Write a function `is_palindrome(txt)` that returns True if the string is a palindrome.",
                "def is_palindrome(txt):\n    pass",
                "assert is_palindrome('madam') is True\nassert is_palindrome('racecar') is True\nassert is_palindrome('hello') is False"
            ),
            (
                "Count Vowels",
                "Write a function `count_vowels(txt)` that returns the number of vowels (a, e, i, o, u) in a string.",
                "def count_vowels(txt):\n    pass",
                "assert count_vowels('Celebration') == 5\nassert count_vowels('Palm') == 1"
            ),
            (
                "Fibonacci",
                "Write a function `fib(n)` that returns the nth Fibonacci number.",
                "def fib(n):\n    pass",
                "assert fib(0) == 0\nassert fib(1) == 1\nassert fib(2) == 1\nassert fib(6) == 8"
            ),
             (
                "Anagram Check",
                "Write a function `is_anagram(s1, s2)` that returns True if s1 and s2 are anagrams.",
                "def is_anagram(s1, s2):\n    pass",
                "assert is_anagram('listen', 'silent') is True\nassert is_anagram('hello', 'world') is False"
            ),
            (
                "Sum of Digits",
                "Write a function `sum_digits(n)` that returns the sum of the digits of a positive integer.",
                "def sum_digits(n):\n    pass",
                "assert sum_digits(123) == 6\nassert sum_digits(90) == 9"
            ),
            (
                "Filter Even Numbers",
                "Write a function `filter_even(lst)` that returns a list containing only the even numbers from the input list.",
                "def filter_even(lst):\n    pass",
                "assert filter_even([1, 2, 3, 4]) == [2, 4]\nassert filter_even([5, 7, 9]) == []"
            ),
            (
                "FizzBuzz",
                "Write a function `fizz_buzz(n)` that returns 'Fizz' if n is divisible by 3, 'Buzz' if by 5, 'FizzBuzz' if by both, else n as a string.",
                "def fizz_buzz(n):\n    pass",
                "assert fizz_buzz(3) == 'Fizz'\nassert fizz_buzz(5) == 'Buzz'\nassert fizz_buzz(15) == 'FizzBuzz'\nassert fizz_buzz(4) == '4'"
            ),
            (
                "Sort List",
                "Write a function `sort_list(lst)` that returns the list sorted in ascending order.",
                "def sort_list(lst):\n    pass",
                "assert sort_list([3, 1, 4, 2]) == [1, 2, 3, 4]\nassert sort_list([9, 8, 7]) == [7, 8, 9]"
            )
        ]

        # Populate defined tasks
        for i, (title, desc, code, test) in enumerate(tasks, 1):
            Challenge.objects.update_or_create(
                order=i,
                defaults={
                    'title': title,
                    'slug': slugify(title),
                    'description': desc,
                    'initial_code': code,
                    'test_code': test,
                    'xp_reward': 50 + (i * 5)
                }
            )

        self.stdout.write(self.style.SUCCESS('Successfully populated 25 challenges'))
