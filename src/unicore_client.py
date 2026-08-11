from __future__ import annotations

import argparse
import asyncio
import json
import sys

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Literal

from mcp import Client, ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.server import mcp


def to_jsonable(
    value: Any,
) -> Any:
    """
    Convierte objetos del SDK MCP / Pydantic
    en estructuras imprimibles como JSON.
    """

    if value is None:
        return None

    if hasattr(
        value,
        "model_dump",
    ):
        return value.model_dump(
            mode="json",
            by_alias=True,
        )

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): to_jsonable(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            to_jsonable(
                item
            )
            for item in value
        ]

    return str(
        value
    )


def parse_text_content(
    text: str,
) -> Any:
    """
    Si un Resource o Tool devuelve JSON como texto,
    intenta reconstruir el objeto Python.

    Si no es JSON válido, conserva el texto.
    """

    clean_text = text.strip()

    if not clean_text:
        return ""

    try:
        return json.loads(
            clean_text
        )
    except json.JSONDecodeError:
        return clean_text


class UniCoreMCPClient:
    """
    Cliente MCP propio de UniCore.

    Soporta dos transportes locales:

    - inprocess:
      conecta directamente con el objeto MCPServer.
      Es el modo por defecto y se mantiene para tests,
      evals y ejecución interna.

    - stdio:
      lanza UniCore como un proceso MCP separado y se
      comunica mediante stdin/stdout.

    Streamable HTTP queda fuera de esta fase de forma
    intencionada.
    """

    def __init__(
        self,
        transport: Literal[
            "inprocess",
            "stdio",
        ] = "inprocess",
    ) -> None:
        if transport not in {
            "inprocess",
            "stdio",
        }:
            raise ValueError(
                "transport debe ser "
                "'inprocess' o 'stdio'"
            )

        self.transport = transport

        self._exit_stack: (
            AsyncExitStack | None
        ) = None

        self._initialize_result: Any = None

        self.client: (
            Client | ClientSession | None
        ) = None

    async def __aenter__(
        self,
    ) -> "UniCoreMCPClient":
        self._exit_stack = (
            AsyncExitStack()
        )

        await self._exit_stack.__aenter__()

        if self.transport == "inprocess":
            client = Client(
                mcp
            )

            self.client = (
                await self._exit_stack
                .enter_async_context(
                    client
                )
            )

            return self

        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        server_parameters = (
            StdioServerParameters(
                command=sys.executable,
                args=[
                    "-m",
                    "src.server",
                ],
                cwd=str(
                    project_root
                ),
            )
        )

        read_stream, write_stream = (
            await self._exit_stack
            .enter_async_context(
                stdio_client(
                    server_parameters
                )
            )
        )

        session = ClientSession(
            read_stream,
            write_stream,
        )

        self.client = (
            await self._exit_stack
            .enter_async_context(
                session
            )
        )

        self._initialize_result = (
            await self.client.initialize()
        )

        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(
                exc_type,
                exc_value,
                traceback,
            )

        self._exit_stack = None
        self._initialize_result = None
        self.client = None

    def require_client(
        self,
    ) -> Client | ClientSession:
        """
        Evita utilizar el cliente fuera del
        bloque async with.
        """

        if self.client is None:
            raise RuntimeError(
                "UniCoreMCPClient no está conectado"
            )

        return self.client

    def _initialize_value(
        self,
        *names: str,
    ) -> Any:
        result = self._initialize_result

        if result is None:
            return None

        for name in names:
            if hasattr(
                result,
                name,
            ):
                return getattr(
                    result,
                    name,
                )

        if hasattr(
            result,
            "model_dump",
        ):
            data = result.model_dump(
                mode="python",
                by_alias=False,
            )

            for name in names:
                if name in data:
                    return data[
                        name
                    ]

            alias_data = (
                result.model_dump(
                    mode="python",
                    by_alias=True,
                )
            )

            for name in names:
                if name in alias_data:
                    return alias_data[
                        name
                    ]

        return None

    async def server_metadata(
        self,
    ) -> dict:
        """
        Devuelve información sobre la conexión MCP.
        """

        client = self.require_client()

        if self.transport == "inprocess":
            return {
                "transport": (
                    self.transport
                ),
                "protocol_version": (
                    client.protocol_version
                ),
                "server_info": (
                    to_jsonable(
                        client.server_info
                    )
                ),
                "server_capabilities": (
                    to_jsonable(
                        client.server_capabilities
                    )
                ),
                "instructions": (
                    client.instructions
                ),
            }

        return {
            "transport": (
                self.transport
            ),
            "protocol_version": (
                self._initialize_value(
                    "protocolVersion",
                    "protocol_version",
                )
            ),
            "server_info": (
                to_jsonable(
                    self._initialize_value(
                        "serverInfo",
                        "server_info",
                    )
                )
            ),
            "server_capabilities": (
                to_jsonable(
                    self._initialize_value(
                        "capabilities",
                    )
                )
            ),
            "instructions": (
                self._initialize_value(
                    "instructions",
                )
            ),
        }

    async def list_tools(
        self,
    ) -> list[dict]:
        """
        Descubre las Tools públicas disponibles.
        """

        client = self.require_client()

        result = await client.list_tools()

        tools = []

        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "title": (
                    tool.title
                ),
                "description": (
                    tool.description
                ),
                "input_schema": (
                    to_jsonable(
                        tool.input_schema
                    )
                ),
                "output_schema": (
                    to_jsonable(
                        tool.output_schema
                    )
                    if hasattr(
                        tool,
                        "output_schema",
                    )
                    else None
                ),
            })

        return tools

    async def list_resources(
        self,
    ) -> list[dict]:
        """
        Descubre Resources directos.
        """

        client = self.require_client()

        result = (
            await client.list_resources()
        )

        resources = []

        for resource in result.resources:
            resources.append({
                "name": resource.name,
                "title": (
                    resource.title
                ),
                "uri": str(
                    resource.uri
                ),
                "description": (
                    resource.description
                ),
                "mime_type": (
                    resource.mime_type
                ),
            })

        return resources

    async def list_resource_templates(
        self,
    ) -> list[dict]:
        """
        Descubre Resources parametrizados.
        """

        client = self.require_client()

        result = (
            await client
            .list_resource_templates()
        )

        templates = []

        for template in (
            result.resource_templates
        ):
            templates.append({
                "name": template.name,
                "title": (
                    template.title
                ),
                "uri_template": str(
                    template.uri_template
                ),
                "description": (
                    template.description
                ),
                "mime_type": (
                    template.mime_type
                ),
            })

        return templates

    async def list_prompts(
        self,
    ) -> list[dict]:
        """
        Descubre Prompts públicos.

        En UniCore permanecen desactivados
        intencionadamente.
        """

        client = self.require_client()

        result = (
            await client.list_prompts()
        )

        prompts = []

        for prompt in result.prompts:
            prompts.append({
                "name": prompt.name,
                "title": (
                    prompt.title
                ),
                "description": (
                    prompt.description
                ),
                "arguments": (
                    to_jsonable(
                        prompt.arguments
                    )
                ),
            })

        return prompts

    async def discover(
        self,
    ) -> dict:
        """
        Realiza discovery completo del servidor.
        """

        metadata = (
            await self.server_metadata()
        )

        tools = (
            await self.list_tools()
        )

        resources = (
            await self.list_resources()
        )

        templates = (
            await self
            .list_resource_templates()
        )

        prompts = (
            await self.list_prompts()
        )

        return {
            "ok": True,
            "connection": metadata,
            "counts": {
                "tools": len(
                    tools
                ),
                "resources": len(
                    resources
                ),
                "resource_templates": len(
                    templates
                ),
                "prompts": len(
                    prompts
                ),
            },
            "tools": tools,
            "resources": resources,
            "resource_templates": (
                templates
            ),
            "prompts": prompts,
        }

    async def read_resource(
        self,
        uri: str,
    ) -> dict:
        """
        Lee un Resource a través del cliente MCP.
        """

        client = self.require_client()

        result = (
            await client.read_resource(
                uri
            )
        )

        contents = []

        for content in result.contents:
            item = {
                "uri": (
                    str(content.uri)
                    if hasattr(
                        content,
                        "uri",
                    )
                    else uri
                ),
                "mime_type": (
                    getattr(
                        content,
                        "mime_type",
                        None,
                    )
                ),
            }

            if hasattr(
                content,
                "text",
            ):
                item[
                    "data"
                ] = parse_text_content(
                    content.text
                )

            elif hasattr(
                content,
                "blob",
            ):
                item[
                    "data"
                ] = {
                    "binary": True,
                    "size": len(
                        content.blob
                    ),
                }

            else:
                item[
                    "data"
                ] = to_jsonable(
                    content
                )

            contents.append(
                item
            )

        return {
            "ok": True,
            "uri": uri,
            "content_count": len(
                contents
            ),
            "contents": contents,
        }

    async def call_tool(
        self,
        name: str,
        arguments: dict | None = None,
    ) -> dict:
        """
        Ejecuta una Tool a través del cliente MCP.
        """

        client = self.require_client()

        result = await client.call_tool(
            name,
            arguments or {},
        )

        structured_content = (
            getattr(
                result,
                "structured_content",
                None,
            )
        )

        if (
            structured_content is None
            and hasattr(
                result,
                "structuredContent",
            )
        ):
            structured_content = (
                result.structuredContent
            )

        text_content = []

        for content in result.content:
            if hasattr(
                content,
                "text",
            ):
                text_content.append(
                    parse_text_content(
                        content.text
                    )
                )
            else:
                text_content.append(
                    to_jsonable(
                        content
                    )
                )

        if structured_content is not None:
            data = to_jsonable(
                structured_content
            )

        elif len(
            text_content
        ) == 1:
            data = text_content[0]

        else:
            data = text_content

        is_error = bool(
            getattr(
                result,
                "is_error",
                getattr(
                    result,
                    "isError",
                    False,
                ),
            )
        )

        return {
            "ok": not is_error,
            "mcp_is_error": is_error,
            "tool": name,
            "data": data,
        }


async def run_catalog(
    transport: str,
) -> None:
    """
    Muestra un catálogo compacto,
    no todos los schemas completos.
    """

    async with UniCoreMCPClient(transport=transport) as client:
        discovery = (
            await client.discover()
        )

        compact = {
            "ok": True,
            "connection": (
                discovery[
                    "connection"
                ]
            ),
            "counts": (
                discovery[
                    "counts"
                ]
            ),
            "tool_names": [
                tool["name"]
                for tool in (
                    discovery[
                        "tools"
                    ]
                )
            ],
            "resources": [
                resource["uri"]
                for resource in (
                    discovery[
                        "resources"
                    ]
                )
            ],
            "resource_templates": [
                template[
                    "uri_template"
                ]
                for template in (
                    discovery[
                        "resource_templates"
                    ]
                )
            ],
            "prompt_names": [
                prompt["name"]
                for prompt in (
                    discovery[
                        "prompts"
                    ]
                )
            ],
        }

        print(
            json.dumps(
                compact,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


async def run_resource(
    uri: str,
    transport: str,
) -> None:
    async with UniCoreMCPClient(transport=transport) as client:
        result = (
            await client.read_resource(
                uri
            )
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


async def run_tool(
    name: str,
    arguments_text: str,
    transport: str,
) -> None:
    try:
        arguments = json.loads(
            arguments_text
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            "Los argumentos de la Tool "
            "deben ser JSON válido"
        ) from error

    if not isinstance(
        arguments,
        dict,
    ):
        raise ValueError(
            "Los argumentos deben ser "
            "un objeto JSON"
        )

    async with UniCoreMCPClient(transport=transport) as client:
        result = await client.call_tool(
            name,
            arguments,
        )

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


async def run_smoke_test(
    transport: str,
) -> None:
    """
    Validación integral del MCP Client.

    Comprueba:
    - conexión MCP
    - discovery
    - catálogo público
    - Tools ocultas
    - Resources
    - Resource Templates
    - Prompts
    - lectura real
    - ejecución real de Tools
    """

    async with UniCoreMCPClient(transport=transport) as client:
        discovery = (
            await client.discover()
        )

        tool_names = {
            tool["name"]
            for tool in (
                discovery[
                    "tools"
                ]
            )
        }

        resource_uris = {
            resource["uri"]
            for resource in (
                discovery[
                    "resources"
                ]
            )
        }

        template_uris = {
            template[
                "uri_template"
            ]
            for template in (
                discovery[
                    "resource_templates"
                ]
            )
        }

        prompt_names = {
            prompt["name"]
            for prompt in (
                discovery[
                    "prompts"
                ]
            )
        }

        checks: list[dict] = []

        def add_check(
            name: str,
            passed: bool,
            detail: Any = None,
        ) -> None:
            checks.append({
                "name": name,
                "passed": bool(
                    passed
                ),
                "detail": detail,
            })

        # ==============================================
        # CONEXIÓN Y DISCOVERY
        # ==============================================

        add_check(
            "protocol_version_detected",
            bool(
                discovery[
                    "connection"
                ][
                    "protocol_version"
                ]
            ),
            discovery[
                "connection"
            ][
                "protocol_version"
            ],
        )

        add_check(
            "tools_discovered",
            len(
                tool_names
            ) > 0,
            len(
                tool_names
            ),
        )

        add_check(
            "resources_discovered",
            len(
                resource_uris
            ) > 0,
            len(
                resource_uris
            ),
        )

        add_check(
            "templates_discovered",
            len(
                template_uris
            ) > 0,
            len(
                template_uris
            ),
        )

        # ==============================================
        # TOOLS IMPORTANTES
        # ==============================================

        required_tools = {
            "health_check",
            "recommend_next_actions",
            "sync_knowledge_map_tool",
        }

        for required_tool in sorted(
            required_tools
        ):
            add_check(
                (
                    "required_tool:"
                    f"{required_tool}"
                ),
                required_tool
                in tool_names,
            )

        # ==============================================
        # TOOLS QUE DEBEN SEGUIR OCULTAS
        # ==============================================

        hidden_tools = {
            "list_subjects",
            "get_subject",
            "list_documents",
            "get_document",
            "get_learning_analytics",
        }

        for hidden_tool in sorted(
            hidden_tools
        ):
            add_check(
                (
                    "hidden_tool_absent:"
                    f"{hidden_tool}"
                ),
                hidden_tool
                not in tool_names,
            )

        # ==============================================
        # RESOURCES IMPORTANTES
        # ==============================================

        add_check(
            "tasks_resource_present",
            "unicore://tasks"
            in resource_uris,
        )

        add_check(
            "documents_resource_present",
            "unicore://documents"
            in resource_uris,
        )

        knowledge_template = (
            "unicore://subjects/"
            "{subject_id}/knowledge"
        )

        add_check(
            "knowledge_template_present",
            knowledge_template
            in template_uris,
            sorted(
                template_uris
            ),
        )

        # ==============================================
        # PROMPTS
        # ==============================================

        add_check(
            "prompts_still_disabled",
            len(
                prompt_names
            ) == 0,
            len(
                prompt_names
            ),
        )

        # ==============================================
        # TOOL REAL
        # ==============================================

        health_result = (
            await client.call_tool(
                "health_check",
                {},
            )
        )

        add_check(
            "health_check_call",
            health_result[
                "ok"
            ],
            health_result[
                "data"
            ],
        )

        # ==============================================
        # RESOURCE REAL
        # ==============================================

        knowledge_result = (
            await client.read_resource(
                (
                    "unicore://subjects/"
                    "1/knowledge"
                )
            )
        )

        add_check(
            "knowledge_resource_read",
            (
                knowledge_result[
                    "ok"
                ]
                and knowledge_result[
                    "content_count"
                ] > 0
            ),
        )

        # ==============================================
        # DECISION ENGINE REAL
        # ==============================================

        decision_result = (
            await client.call_tool(
                "recommend_next_actions",
                {
                    "available_minutes": 60,
                    "subject_id": 1,
                    "maximum_actions": 3,
                },
            )
        )

        add_check(
            "decision_engine_call",
            decision_result[
                "ok"
            ],
        )

        decision_text = json.dumps(
            decision_result[
                "data"
            ],
            ensure_ascii=False,
            default=str,
        )

        add_check(
            "decision_engine_returns_subject",
            (
                "Dirección Estratégica"
                in decision_text
            ),
        )

        # ==============================================
        # RESULTADO FINAL
        # ==============================================

        failed_checks = [
            check
            for check in checks
            if not check[
                "passed"
            ]
        ]

        result = {
            "ok": (
                len(
                    failed_checks
                )
                == 0
            ),
            "summary": {
                "protocol_version": (
                    discovery[
                        "connection"
                    ][
                        "protocol_version"
                    ]
                ),
                "tool_count": (
                    discovery[
                        "counts"
                    ][
                        "tools"
                    ]
                ),
                "resource_count": (
                    discovery[
                        "counts"
                    ][
                        "resources"
                    ]
                ),
                "resource_template_count": (
                    discovery[
                        "counts"
                    ][
                        "resource_templates"
                    ]
                ),
                "prompt_count": (
                    discovery[
                        "counts"
                    ][
                        "prompts"
                    ]
                ),
                "check_count": len(
                    checks
                ),
                "failed_check_count": len(
                    failed_checks
                ),
            },
            "checks": checks,
        }

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


def build_parser(
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cliente MCP propio de UniCore"
        )
    )

    parser.add_argument(
        "--transport",
        choices=(
            "inprocess",
            "stdio",
        ),
        default="inprocess",
        help=(
            "Transporte MCP local. "
            "Por defecto: inprocess."
        ),
    )

    subparsers = (
        parser.add_subparsers(
            dest="command",
            required=True,
        )
    )

    subparsers.add_parser(
        "catalog",
        help=(
            "Descubre Tools, Resources, "
            "Templates y Prompts"
        ),
    )

    resource_parser = (
        subparsers.add_parser(
            "resource",
            help=(
                "Lee un Resource MCP"
            ),
        )
    )

    resource_parser.add_argument(
        "uri",
        help="URI del Resource",
    )

    tool_parser = (
        subparsers.add_parser(
            "tool",
            help=(
                "Ejecuta una Tool MCP"
            ),
        )
    )

    tool_parser.add_argument(
        "name",
        help="Nombre de la Tool",
    )

    tool_parser.add_argument(
        "arguments",
        nargs="?",
        default="{}",
        help=(
            "Argumentos como JSON"
        ),
    )
    tool_parser.add_argument(
        "--available-minutes",
        type=int,
        default=None,
        help=(
            "Minutos disponibles para Tools "
            "que acepten este parámetro"
        ),
    )

    tool_parser.add_argument(
        "--subject-id",
        type=int,
        default=None,
        help=(
            "ID de asignatura para Tools "
            "que acepten este parámetro"
        ),
    )

    tool_parser.add_argument(
        "--maximum-actions",
        type=int,
        default=None,
        help=(
            "Máximo de acciones para el "
            "Decision Engine"
        ),
    )

    subparsers.add_parser(
        "smoke",
        help=(
            "Ejecuta la validación "
            "integral del cliente"
        ),
    )

    return parser


async def async_main(
) -> None:
    parser = build_parser()

    args = parser.parse_args()

    if args.command == "catalog":
        await run_catalog(
            args.transport
        )
        return

    if args.command == "resource":
        await run_resource(
            args.uri,
            args.transport,
        )
        return

    if args.command == "tool":
        tool_arguments = args.arguments

        named_arguments = {}

        if (
            args.available_minutes
            is not None
        ):
            named_arguments[
                "available_minutes"
            ] = args.available_minutes

        if (
            args.subject_id
            is not None
        ):
            named_arguments[
                "subject_id"
            ] = args.subject_id

        if (
            args.maximum_actions
            is not None
        ):
            named_arguments[
                "maximum_actions"
            ] = args.maximum_actions

        if named_arguments:
            tool_arguments = json.dumps(
                named_arguments
            )

        await run_tool(
            args.name,
            tool_arguments,
            args.transport,
        )
        return

    if args.command == "smoke":
        await run_smoke_test(
            args.transport
        )
        return

    parser.error(
        "Comando desconocido"
    )


def main(
) -> None:
    asyncio.run(
        async_main()
    )


if __name__ == "__main__":
    main()