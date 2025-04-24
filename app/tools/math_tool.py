#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Math Tool for Number Ninja agent.

This tool provides basic math calculation capabilities that can be used
before resorting to the LLM for more complex problems.
"""

import re
import math
from typing import Dict, Any, Optional, Union, Tuple
from langchain_community.tools import Tool

# Math operations patterns
OPERATIONS = ['+', '-', '*', '/', '^', '**']


class MathToolFunctions:
    """Function implementations for the math tool."""
    
    @staticmethod
    def process_math_query(query: str) -> Dict[str, Any]:
        """
        Process a math query and attempt to solve it.
        
        Args:
            query: The mathematical query to process.
            
        Returns:
            Dictionary with the solution details.
        """
        # First check if this is a math query
        if not MathToolFunctions.is_math_query(query):
            return {
                "is_math_tool_query": False,
                "message": "This is not a math query.",
                "answer": "I don't know",
                "explanation": None,
                "needs_more_info": False,
                "response_score": 0.0
            }
        
        # Look for specific math function mentions
        if any(term in query.lower() for term in ['square root', 'sqrt', 'derivative', 'integrate', 'logarithm', 'sin', 'cos', 'tan', 'differentiate']):
            # Check for derivatives specifically
            derivative_pattern = r'(derivative|differentiate)\s+(of\s+)?([\w\^\d\+\-\*\/\(\)\s]+)'  
            if match := re.search(derivative_pattern, query.lower()):
                function_to_differentiate = match.group(3) if match.group(3) else "the function"
                return {
                    "is_math_tool_query": True,
                    "message": f"This requires calculating the derivative of {function_to_differentiate}.",
                    "answer": "I don't know.",
                    "explanation": None,
                    "needs_more_info": False,
                    "requires_llm": True,
                    "response_score": 0.0
                }
                
            # Extract square root specifically since it's common
            sqrt_pattern = r'(square\s+root|sqrt)\s+of\s+(\d+)'
            if match := re.search(sqrt_pattern, query.lower()):
                try:
                    num = float(match.group(2))
                    result = math.sqrt(num)
                    return {
                        "is_math_tool_query": True,
                        "message": "Successfully calculated the square root.",
                        "answer": str(result),
                        "explanation": None,
                        "needs_more_info": False,
                        "response_score": 100
                    }
                except:
                    pass
            # For other special functions, use LLM
            return {
                "is_math_tool_query": True,
                "message": "This requires a special math function calculation.",
                "answer": "I don't know.",
                "explanation": None,
                "needs_more_info": False,
                "requires_llm": True,
                "response_score": 0.0
            }
            
        # Check if it's a simple calculation or has numerical operators
        # Try evaluating as a direct expression
        success, result = MathToolFunctions.try_evaluate_expression(query)
        if success:
            return {
                "is_math_tool_query": True,
                "message": "Successfully calculated the result.",
                "answer": str(result),
                "explanation": None,  # No explanation needed for simple calculations
                "needs_more_info": False,
                "response_score": 1.0
            }
        
        # Check if it's an equation (contains = sign)
        if "=" in query:
            success, result = MathToolFunctions.solve_basic_equation(query)
            if success:
                return {
                    "is_math_tool_query": True,
                    "message": "Successfully solved the equation.",
                    "answer": result,
                    "explanation": "I rearranged the equation to solve for the variable.",
                    "needs_more_info": False,
                    "response_score": 1.0
                }
        
        # If we reached here, we couldn't solve it with our simple tools
        return {
            "is_math_tool_query": True,
            "message": "This math problem requires more advanced techniques.",
            "answer": "I don't know",
            "explanation": None,
            "needs_more_info": False,
            "requires_llm": True,  # Flag to indicate we should use the LLM
            "response_score": 0.0
        }
    
    @staticmethod
    def is_math_query(query: str) -> bool:
        """
        Determine if a query is math-related.
        
        Args:
            query: The query string to check.
            
        Returns:
            True if the query is math-related, False otherwise.
        """
        # Clean the query first
        cleaned_query = query.lower().strip()
        
        # Create a version with no spaces for exact pattern matching
        no_spaces_query = re.sub(r'\s+', '', cleaned_query)
        
        # Check for non-math queries first
        non_math_indicators = [
            "capital of", "president of", "population of", 
            "who is", "who was", "where is", "when did", 
            "history of", "definition of", "meaning of", "weather",
            "explain", "describe", "tell me about", "what are", "news"
        ]
        
        for indicator in non_math_indicators:
            if indicator in cleaned_query:
                # Likely a general knowledge question, not math
                return False
        
        # Basic pattern for detecting common math operations and terms
        no_spaces_patterns = [
            r'\d+[\+\-\*\/\^]\d+',              # Numbers with operators (no spaces)
        ]
        
        # Check no-spaces patterns against no_spaces_query
        for pattern in no_spaces_patterns:
            if re.search(pattern, no_spaces_query):
                return True
        
        # Check regular patterns against cleaned_query
        spaced_patterns = [
            r'\d+\s*[\+\-\*\/\^]\s*\d+',        # Numbers with operators between them
            r'calculate\s+\d+', r'compute\s+\d+',   # Calculate/compute with numbers
            r'solve\s+.{0,10}=',                     # Solve with = sign nearby
            r'what\s+is\s+\d+\s*[\+\-\*\/\^]',     # "What is" followed by number and operator
            r'\d+\s*\+\s*\d+',                     # Addition
            r'\d+\s*\-\s*\d+',                     # Subtraction
            r'\d+\s*\*\s*\d+',                     # Multiplication
            r'\d+\s*\/\s*\d+',                     # Division
            r'\d+\s*\^\s*\d+',                     # Exponentiation
            r'square\s+root\s+of\s+\d+',           # Square root
            r'\b\d+\s*times\s*\d+\b',              # Times as multiplication
            r'\bdivided\s+by\b',                    # Division
            r'\bplus\b', r'\bminus\b',               # Plus/minus
            r'\bequation\b', r'\bformula\b',        # Equation/formula terms
            r'\(\s*\d+[\+\-\*\/\^]',              # Parentheses with math
            r'\bx\s*[\+\-\*\/]\s*\d+\s*=',        # Algebraic equations
            r'\bx\s*=',                             # x = something
            r'derivative\s+of',                     # Derivatives
            r'integral\s+of',                       # Integrals
            r'differentiate',                       # Differentiation
            r'integrate',                           # Integration
            r'logarithm',                           # Logarithms
            r'\b(sin|cos|tan)\b',                   # Trigonometric functions
            r'\bx\^\d+\b',                        # x raised to power
            r'\blimit\b',                           # Limits
        ]
        
        # Check regular patterns against cleaned_query
        for pattern in spaced_patterns:
            if re.search(pattern, cleaned_query):
                return True
        
        # Check for specific math-related words when there are numbers in the query
        if re.search(r'\d+', cleaned_query) or re.search(r'\b[xyz]\b', cleaned_query):
            math_keywords = [
                "add", "sum", "plus", "subtract", "minus", "multiply", "divide", 
                "calculate", "compute", "evaluate", "solve", "equation", "equals",
                "squared", "cubed", "power", "root", "percentage", "factorial",
                "derivative", "integral", "differentiate", "integrate", "logarithm",
                "sin", "cos", "tan", "sine", "cosine", "tangent", "limit",
                "calculus", "algebra", "polynomial", "function"
            ]
            
            for keyword in math_keywords:
                if keyword in cleaned_query:
                    return True
        
        return False
    
    @staticmethod
    def try_evaluate_expression(expression: str) -> Tuple[bool, Optional[Union[float, str]]]:
        """
        Attempt to evaluate a simple mathematical expression.
        
        Args:
            expression: A mathematical expression as a string.
            
        Returns:
            Tuple of (success, result or error message)
        """
        # Clean up the expression
        cleaned = expression.lower().strip()
        
        # Extract numbers and operations from natural language
        # Handle "what is X plus/minus/times/divided by Y"
        what_is_pattern = r'what\s+is\s+(\d+)\s*(plus|minus|times|divided by|\+|\-|\*|\/)\s*(\d+)'  
        if match := re.search(what_is_pattern, cleaned):
            num1, op, num2 = match.groups()
            if op == 'plus': op = '+'
            elif op == 'minus': op = '-'
            elif op == 'times': op = '*'
            elif op == 'divided by': op = '/'
            cleaned = f"{num1} {op} {num2}"
        
        # Replace common math words with symbols
        word_replacements = {
            'plus': '+',
            'minus': '-',
            'times': '*',
            'multiplied by': '*',
            'divided by': '/',
            'over': '/',
            'to the power of': '**',
            'squared': '**2',
            'cubed': '**3',
        }
        
        for word, symbol in word_replacements.items():
            cleaned = re.sub(rf'\b{word}\b', symbol, cleaned, flags=re.IGNORECASE)
        
        # Handle "calculate X + Y" or "compute X * Y"
        calc_pattern = r'(calculate|compute|evaluate)\s+(.+)'
        if match := re.search(calc_pattern, cleaned):
            cleaned = match.group(2)
        
        # Extract just the math expression if embedded in text
        math_regex = r'[\d\+\-\*\/\^\(\)=\.\s]+'
        matches = re.findall(math_regex, cleaned)
        
        if not matches:
            return False, "No valid mathematical expression found"
        
        # Get the last match (in case there are multiple)
        math_expr = matches[-1].strip()
        
        # Remove all spaces from the expression
        math_expr = re.sub(r'\s+', '', math_expr)
        
        try:
            # Evaluate the expression
            result = eval(math_expr)
            return True, result
        except Exception as e:
            return False, f"Error evaluating expression: {str(e)}"
    
    @staticmethod
    def solve_basic_equation(equation: str) -> Tuple[bool, Optional[str]]:
        """
        Solve a very basic equation of the form x + a = b or a * x = b.
        
        Args:
            equation: The equation string to solve.
            
        Returns:
            Tuple of (success, result string if successful)
        """
        # Normalize the equation
        equation = equation.lower().strip()
        
        # Extract the equation if it's embedded in a sentence
        eq_pattern = r'([a-z\d\s\+\-\*\/\^\(\)=\.]+\s*=\s*[a-z\d\s\+\-\*\/\^\(\)\.]+)'
        eq_matches = re.findall(eq_pattern, equation)
        if eq_matches:
            equation = max(eq_matches, key=len).strip()
        
        # Replace text operations with symbols
        operation_replacements = {
            'plus': '+',
            'minus': '-',
            'times': '*',
            'multiplied by': '*',
            'divided by': '/',
        }
        
        for word, symbol in operation_replacements.items():
            equation = re.sub(rf'\b{word}\b', symbol, equation, flags=re.IGNORECASE)
        
        # Handle "solve for x in x + 5 = 10"
        solve_pattern = r'solve\s+for\s+([a-z])\s+in\s+(.+)'
        if match := re.search(solve_pattern, equation):
            equation = match.group(2)
        
        # Very basic parsing for solving equations like "x + 5 = 10" or "2x = 8"
        # Split by equals sign
        if '=' not in equation:
            return False, None
        
        left, right = equation.split('=', 1)
        left = left.strip()
        right = right.strip()
        
        # Try to find the variable (looking for a letter followed by nothing or a number)
        var_pattern = r'([a-z])(?:\s*[\+\-\*\/]\s*|$|\s*=)'
        var_match = re.search(var_pattern, left)
        if not var_match:
            # Check the right side
            var_match = re.search(var_pattern, right)
            if not var_match:
                return False, None
        
        variable = var_match.group(1)
        
        try:
            # Handle very basic cases:
            # Case 1: x + a = b => x = b - a
            pattern1 = rf'{variable}\s*\+\s*(\d+\.?\d*)\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern1, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b - a
                return True, f"{variable} = {result}"
            
            # Case 2: a + x = b => x = b - a
            pattern2 = rf'(\d+\.?\d*)\s*\+\s*{variable}\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern2, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b - a
                return True, f"{variable} = {result}"
            
            # Case 3: x - a = b => x = b + a
            pattern3 = rf'{variable}\s*\-\s*(\d+\.?\d*)\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern3, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b + a
                return True, f"{variable} = {result}"
            
            # Case 4: a - x = b => x = a - b
            pattern4 = rf'(\d+\.?\d*)\s*\-\s*{variable}\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern4, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = a - b
                return True, f"{variable} = {result}"
            
            # Case 5: a * x = b => x = b / a
            pattern5 = rf'(\d+\.?\d*)\s*[\*]\s*{variable}\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern5, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b / a
                return True, f"{variable} = {result}"
            
            # Case 6: x * a = b => x = b / a
            pattern6 = rf'{variable}\s*[\*]\s*(\d+\.?\d*)\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern6, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b / a
                return True, f"{variable} = {result}"
            
            # Case 7: x / a = b => x = b * a
            pattern7 = rf'{variable}\s*[\/]\s*(\d+\.?\d*)\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern7, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b * a
                return True, f"{variable} = {result}"
            
            # Case 8: a / x = b => x = a / b
            pattern8 = rf'(\d+\.?\d*)\s*[\/]\s*{variable}\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern8, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = a / b
                return True, f"{variable} = {result}"
            
            # Case 9: ax = b => x = b/a (coefficient form)
            pattern9 = rf'(\d+\.?\d*)\s*{variable}\s*=\s*(\d+\.?\d*)'
            if match := re.search(pattern9, equation):
                a, b = float(match.group(1)), float(match.group(2))
                result = b / a
                return True, f"{variable} = {result}"
            
            return False, None
        except Exception as e:
            return False, None


# Create a tool for math operations
math_tool = Tool(
    name="math_calculator",
    func=MathToolFunctions.process_math_query,
    description="A math tool that can quickly solve basic math queries including arithmetic operations, simple equations, and some special operations like square roots."
)
