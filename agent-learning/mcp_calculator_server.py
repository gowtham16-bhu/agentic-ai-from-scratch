import ast
import operator
from mcp.server.fastmcp import FastMCP

# Same safe_eval from step2 -- MCP doesn't change the tool's internals,
# only how other programs discover and call it.
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](safe_eval(node.operand))
    raise ValueError("unsupported expression")

mcp = FastMCP("calculator-server")

@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate arithmetic. Example: '47 * 89' -> '4183'. Supports + - * / ** ()."""
    try:
        return str(safe_eval(ast.parse(expression, mode="eval").body))
    except Exception:
        return f"error: could not parse '{expression}' as arithmetic."

@mcp.tool()
def word_count(text: str) -> str:
    """Count the number of words in a string."""
    return str(len(text.split()))

if __name__ == "__main__":
    mcp.run()
