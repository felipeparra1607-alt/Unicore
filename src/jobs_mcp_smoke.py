from __future__ import annotations

import asyncio
import json

from src.capability_router import (
    build_capability_selection,
)

from src.unicore_client import (
    UniCoreMCPClient,
)


async def main(
) -> None:
    async with (
        UniCoreMCPClient()
        as client
    ):
        discovery = (
            await client.discover()
        )

        tool_names = {
            tool[
                "name"
            ]
            for tool
            in discovery[
                "tools"
            ]
        }

        direct_resource_uris = {
            resource[
                "uri"
            ]
            for resource
            in discovery[
                "resources"
            ]
        }

        template_uris = {
            template[
                "uri_template"
            ]
            for template
            in discovery[
                "resource_templates"
            ]
        }

        checks = []

        checks.append({
            "name": (
                "get_job_status_public"
            ),
            "passed": (
                "get_job_status"
                in tool_names
            ),
        })

        checks.append({
            "name": (
                "list_jobs_public"
            ),
            "passed": (
                "list_jobs"
                in tool_names
            ),
        })

        checks.append({
            "name": (
                "jobs_resource_present"
            ),
            "passed": (
                "unicore://jobs"
                in direct_resource_uris
            ),
        })

        checks.append({
            "name": (
                "job_template_present"
            ),
            "passed": (
                "unicore://jobs/{job_id}"
                in template_uris
            ),
        })

        jobs_resource = (
            await client.read_resource(
                "unicore://jobs"
            )
        )

        checks.append({
            "name": (
                "jobs_resource_readable"
            ),
            "passed": bool(
                jobs_resource
            ),
        })

        list_result = (
            await client.call_tool(
                "list_jobs",
                {
                    "limit": 5,
                },
            )
        )

        checks.append({
            "name": (
                "list_jobs_callable"
            ),
            "passed": bool(
                list_result
            ),
        })

        selection = (
            build_capability_selection(
                user_request=(
                    "¿Qué Jobs de UniCore "
                    "tengo y cuál fue el último?"
                ),
                allow_writes=False,
            )
        )

        checks.append({
            "name": (
                "router_detects_jobs"
            ),
            "passed": (
                selection[
                    "profiles"
                ]
                == [
                    "jobs"
                ]
            ),
            "detail": (
                selection[
                    "profiles"
                ]
            ),
        })

        checks.append({
            "name": (
                "router_has_jobs_resource"
            ),
            "passed": (
                "unicore://jobs"
                in selection[
                    "direct_resource_uris"
                ]
            ),
        })

        checks.append({
            "name": (
                "router_has_jobs_tools"
            ),
            "passed": (
                {
                    "get_job_status",
                    "list_jobs",
                }
                .issubset(
                    selection[
                        "tool_names"
                    ]
                )
            ),
        })

        failed = [
            check
            for check
            in checks
            if not check[
                "passed"
            ]
        ]

        print(
            json.dumps(
                {
                    "ok": (
                        len(
                            failed
                        )
                        == 0
                    ),
                    "passed_count": (
                        len(checks)
                        - len(failed)
                    ),
                    "failed_count": (
                        len(failed)
                    ),
                    "checks": checks,
                    "discovery_counts": {
                        "tools": len(
                            discovery[
                                "tools"
                            ]
                        ),
                        "resources": len(
                            discovery[
                                "resources"
                            ]
                        ),
                        "templates": len(
                            discovery[
                                "resource_templates"
                            ]
                        ),
                    },
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )