from mcp.server import MCPServer

from mcp.server.mcpserver import (
    Context,
)

from mcp.types import (
    SamplingMessage,
    TextContent,
)


mcp = MCPServer(
    "UniCore Sampling Experiment"
)


@mcp.tool()
async def explain_with_sampling(
    topic: str,
    ctx: Context,
) -> dict:
    """
    Experimento educativo de Sampling legacy.

    El servidor NO llama directamente a un modelo.

    Pide al MCP Client que procese un mensaje
    mediante sampling/createMessage.
    """

    clean_topic = topic.strip()

    if not clean_topic:
        return {
            "ok": False,
            "error": (
                "El tema no puede estar vacío"
            ),
        }

    result = await ctx.session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "Explica brevemente este "
                        "concepto académico:\n\n"
                        f"{clean_topic}"
                    ),
                ),
            )
        ],
        max_tokens=200,
    )

    if result.content.type == "text":
        answer = result.content.text

    else:
        answer = str(
            result.content
        )

    return {
        "ok": True,
        "topic": clean_topic,
        "answer": answer,
        "model": result.model,
        "stop_reason": (
            result.stop_reason
        ),
        "architecture": (
            "MCP Server -> MCP Client "
            "-> sampling callback"
        ),
    }


if __name__ == "__main__":
    mcp.run(
        transport="stdio"
    )