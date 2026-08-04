from mcp.server import MCPServer

mcp = MCPServer("UniCore")


@mcp.tool()
def health_check() -> str:
    """Comprueba que el servidor UniCore está funcionando."""
    return "UniCore MCP funcionando correctamente"