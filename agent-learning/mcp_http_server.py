import ast
import operator
from mcp.server.fastmcp import FastMCP

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

# port=8765 -- this server will listen on http://localhost:8765, a REAL network
# address, unlike stdio which had no address at all (just pipes to a subprocess)
mcp = FastMCP("calculator-http-server", port=8765)


@mcp.tool()
def word_count(text: str) -> str:
    """Count words in text. Example: 'hello world' -> '2 words'."""
    return f"{len(text.split())} words"



@mcp.tool()
def calculator(expression: str) -> str:
    """Evaluate arithmetic. Example: '47 * 89' -> '4183'. Supports + - * / ** ()."""
    try:
        return str(safe_eval(ast.parse(expression, mode="eval").body))
    except Exception:
        return f"error: could not parse '{expression}' as arithmetic."

if __name__ == "__main__":
    mcp.run(transport="sse")  # ONLY LINE THAT CHANGED FROM mcp.run() -- stdio -> sse
