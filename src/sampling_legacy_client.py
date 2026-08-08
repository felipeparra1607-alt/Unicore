import asyncio
import json
import sys

import mcp_types as types

from mcp import (
    ClientSession,
    StdioServerParameters,
)

from mcp.client.context import (
    ClientRequestContext,
)

from mcp.client.stdio import (
    stdio_client,
)


async def handle_sampling_message(
    context: ClientRequestContext,
    params: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    """
    Callback de Sampling del cliente.

    En una aplicación real, aquí el Host
    podría llamar a su LLM.

    En este experimento NO usamos ningún modelo
    ni gastamos tokens: devolvemos una respuesta
    simulada.
    """

    print(
        "\n=== SAMPLING RECIBIDO POR EL CLIENTE ==="
    )

    print(
        f"Mensajes recibidos: "
        f"{len(params.messages)}"
    )

    if params.messages:
        last_message = (
            params.messages[-1]
        )

        print(
            "Último mensaje:"
        )

        print(
            last_message
        )

    print(
        "========================================\n"
    )

    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text=(
                "Respuesta simulada del Host: "
                "Sampling permite que un servidor MCP "
                "solicite al cliente que produzca una "
                "respuesta con su modelo."
            ),
        ),
        model="unicore-fake-model",
        stop_reason="endTurn",
    )


async def run() -> None:
    server_params = (
        StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "src.sampling_experiment",
            ],
        )
    )

    async with stdio_client(
        server_params
    ) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
            sampling_callback=(
                handle_sampling_message
            ),
        ) as session:
            initialize_result = (
                await session.initialize()
            )

            print(
                "=== CLIENTE LEGACY CONECTADO ==="
            )

            print(
                "Servidor:"
            )

            print(
                initialize_result.server_info
            )

            print()

            tools = (
                await session.list_tools()
            )

            print(
                "Tools:"
            )

            print(
                [
                    tool.name
                    for tool in tools.tools
                ]
            )

            print()

            result = (
                await session.call_tool(
                    "explain_with_sampling",
                    arguments={
                        "topic": (
                            "MCP Sampling"
                        ),
                    },
                )
            )

            print(
                "=== RESULTADO DE LA TOOL ==="
            )

            if (
                result.structured_content
                is not None
            ):
                output = (
                    result.structured_content
                )

            else:
                output = [
                    (
                        content.text
                        if isinstance(
                            content,
                            types.TextContent,
                        )
                        else str(content)
                    )
                    for content
                    in result.content
                ]

            print(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )


def main() -> None:
    asyncio.run(
        run()
    )


if __name__ == "__main__":
    main()