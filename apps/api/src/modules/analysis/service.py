"""
C2Pro - Analysis Service

Servicios de negocio para el módulo de análisis, incluyendo validación de expresiones
y la lógica del motor de coherencia.
"""

from lark import Lark, Transformer, v_args
from lark.exceptions import UnexpectedInput

# Define the grammar for the filter expressions
# This grammar supports basic comparisons, 'in' operator, and boolean logic ('and', 'or')
# It allows for variable names, string literals, and numbers.
_FILTER_GRAMMAR = """
    ?start: expr

    ?expr: term (("and" | "or") term)*
    ?term: factor (("==" | "!=" | ">" | "<" | ">=" | "<=") factor)*
         | variable "in" list_
         | "(" expr ")"

    ?factor: variable
           | string_
           | number

    list_: "[" [string_ ("," string_)*] "]"

    variable: /[a-zA-Z_][a-zA-Z0-9_]*/
    string_: /"[^"]*"/ | /'[^']*'/
    number: SIGNED_NUMBER

    %import common.SIGNED_NUMBER
    %import common.WS
    %ignore WS
"""

# Define a set of allowed variables to prevent injection of arbitrary attributes
ALLOWED_FILTER_VARIABLES = {
    "severity",
    "document_type",
    "status",
    "coherence_score",
    "project_name",
    "project_type",
    "created_at",
}

# Define a set of allowed operators
ALLOWED_OPERATORS = {"==", "!=", ">", "<", ">=", "<=", "in", "and", "or"}


# --- Placeholder for a safe expression evaluator (to be implemented later) ---
# This Transformer would convert the parsed AST into a callable function or a safe internal representation.
# For now, we only focus on successful parsing for validation.
@v_args(inline=True)  # Affects the signatures of the methods
class FilterExpressionTransformer(Transformer):
    def string_(self, s):
        return s[1:-1]  # Remove quotes

    def list_(self, *items):
        return list(items)

    def number(self, n):
        return float(n)  # Or int(n) if only integers are expected

    def variable(self, v):
        if v not in ALLOWED_FILTER_VARIABLES:
            raise ValueError(f"Disallowed variable: {v}")
        return str(v)

    # For now, we just pass through operators and structure
    def __default__(self, data, children, meta):
        return (data, children)


_filter_parser = Lark(_FILTER_GRAMMAR, start="expr", parser="earley", propagate_positions=False)


def validate_expression(expression: str) -> bool:
    """
    Validates a filter expression using a secure Lark parser.

    This function checks if the given expression conforms to the predefined grammar
    and uses only allowed variables and operators, preventing arbitrary code execution.

    Args:
        expression: The filter expression string to validate.

    Returns:
        True if the expression is valid and safe, False otherwise.

    Raises:
        (No explicit re-raises, but catches):
            - UnexpectedInput: If the expression does not conform to the grammar.
            - ValueError: If a disallowed variable is found during transformation.
            - Exception: For any other unexpected errors during parsing or transformation.
    """
    try:
        # Parse the expression
        tree = _filter_parser.parse(expression)

        # Transform the tree to perform variable validation
        # This will raise a ValueError if disallowed variables are found
        FilterExpressionTransformer().transform(tree)

        return True
    except UnexpectedInput:
        # The expression does not conform to the grammar
        return False
    except ValueError:
        # A disallowed variable was found during transformation
        return False
    except Exception:
        # Catch any other unexpected errors during parsing or transformation
        return False


# --- Placeholder for other analysis services ---
# e.g., WBSGenerator, BOMGenerator, Scorer, AlertGenerator
