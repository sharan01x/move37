# Move 37 Tools Module

This directory contains tools that enhance the capabilities of Move 37 agents.

## Math Tool

The Math Tool (`math_tool.py`) provides mathematical calculation capabilities to the Move 37 application. It is designed to be used with the FirstResponderAgent to handle mathematical queries directly, without needing to use the LLM.

### Features

- **Math Query Detection**: Identifies whether a query is math-related using pattern matching
- **Expression Evaluation**: Evaluates mathematical expressions (e.g., "2+2", "15/3", "2^3")
- **Equation Solving**: Solves algebraic equations (e.g., "x + 5 = 10")
- **Special Function Support**: Handles special functions like square roots

### Components

#### `MathDetector`

A utility class that determines if a query is math-related based on patterns. It has methods to:

- Check if a string matches common mathematical patterns
- Filter out non-math related queries that might contain numbers (e.g., "World Cup 2018")

#### `MathTool`

A CrewAI-compatible tool that can be attached to an agent. It handles executing math-related queries.

#### `MathToolFunctions`

Contains the core mathematical processing logic:

- Extracting mathematical expressions from text queries
- Solving equations
- Evaluating expressions
- Handling special cases like square roots

### Usage

```python
from app.tools.math_tool import MathDetector, math_tool, MathToolFunctions

# Check if a query is math-related
is_math = MathDetector.is_math_query("What is 2+2?")  # True

# Solve a math problem directly
result = MathToolFunctions.solve_math_problem("What is 2+2?")  # "4"

# To use with an agent:
agent = FirstResponderAgent()  # Already includes math_tool in its tools list
```

### Security

The Math Tool uses a secure approach to evaluating expressions:
- Uses SymPy for symbolic computation as the primary method
- Falls back to a restricted `eval()` only for simple expressions with safe characters
- Implements whitelist-based character filtering to prevent code injection

### Extending the Tool

To add support for new mathematical operations:
1. Update the `MATH_PATTERNS` in `MathDetector` to recognize the new patterns
2. Add handling logic in `MathToolFunctions.solve_math_problem` or create new specialized methods
3. Update tests to cover the new functionality
