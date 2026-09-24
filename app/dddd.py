import uvicorn
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI

# Create MCP server
mcp = FastMCP("Analytics Tools")


def greet(name: str) -> str:
    return f"Hello, {name}!"

mcp.add_tool(greet)


# Create ASGI app from MCP server
mcp_app = mcp.streamable_http_app()

# Key: Pass lifespan to FastAPI
app = FastAPI(title="E-commerce API")

# Mount the MCP server
app.mount("/analytics", mcp_app)

# Now: API at /products/*, MCP at /analytics/mcp/

if __name__ == "__main__":
    uvicorn.run(
        "app.dddd:app",
        host='127.0.0.1',
        port=8000,
    )