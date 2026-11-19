"""Deterministic reference provider using the public Python SDK boundary."""

import argparse
import asyncio
import json
import os
import socket
import ssl
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCard,
    Artifact,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskStatusUpdateEvent,
)
from a2a_schema_contract.core import EXTENSION_URI
from a2a_schema_contract.http import create_app
from a2a_schema_contract.resolver import ContractResolver
from a2a_schema_contract.server import ContractServer, output_artifact, output_message
from google.protobuf.json_format import MessageToDict, ParseDict
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send


class ReferenceAgent(AgentExecutor):
    """Application-owned invoice, presence and echo business behavior."""

    def __init__(self, evidence_enabled: bool = False) -> None:
        self.boundary: ContractServer
        self.evidence_enabled = evidence_enabled
        self.calls: list[dict[str, object]] = []

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        execution = self.boundary.execution(context)
        selection = execution.selection
        contract_id = selection.invocation.contract_id
        settings = context.metadata if self.evidence_enabled else {}
        if self.evidence_enabled:
            call: dict[str, object] = {
                "contractId": contract_id,
                "inputPresent": selection.input.present,
                "inputPartCount": len(context.message.parts) if context.message else 0,
            }
            if selection.output is not None:
                call["outputRepresentationId"] = selection.output.representation.id
            self.calls.append(call)

        if settings.get("fault") == "throw":
            raise RuntimeError("secret-business-value")
        if settings.get("fault") == "wait":
            await event_queue.enqueue_event(
                Task(
                    id=execution.task_id,
                    context_id=execution.context_id,
                    status={"state": "TASK_STATE_WORKING"},
                )
            )
            await execution.cancelled.wait()
            return
        if settings.get("prompt") is True:
            await event_queue.enqueue_event(
                Task(
                    id=execution.task_id,
                    context_id=execution.context_id,
                    status={"state": "TASK_STATE_INPUT_REQUIRED"},
                )
            )
            return

        value: object = None
        output = selection.output
        if output is not None and settings.get("omit") is not True:
            if contract_id == "urn:reference:invoice:1":
                input_value = execution.input
                if isinstance(input_value, str):
                    total: int | float = int(input_value or "0")
                    label = None
                elif isinstance(input_value, dict):
                    quantity, unit_price = (
                        input_value["quantity"],
                        input_value["unitPrice"],
                    )
                    if (
                        isinstance(quantity, bool)
                        or not isinstance(quantity, (int, float))
                        or isinstance(unit_price, bool)
                        or not isinstance(unit_price, (int, float))
                    ):
                        raise TypeError("Expected invoice numbers")
                    total = quantity * unit_price
                    label = input_value["label"]
                else:
                    raise ValueError("Expected invoice input")
                if output.representation.id == "text":
                    value = str(int(total)) if total == int(total) else str(total)
                elif output.representation.id == "compact":
                    value = {"total": total}
                else:
                    value = {"total": total, "label": label}
            elif ":presence-" in contract_id:
                value = {"inputPresent": selection.input.present}
            elif contract_id.startswith("urn:reference:flight-search:"):
                value = {
                    "flights": [
                        {
                            "flightNumber": "REF101",
                            "origin": "BLR",
                            "destination": "DEL",
                        }
                    ]
                }
            else:
                value = execution.input

        if settings.get("message") is True and output is not None:
            await event_queue.enqueue_event(output_message(execution, value))
            return

        if settings.get("fault") == "invalid" and output is not None:
            # Deliberately bypass output helpers to exercise the publication gate.
            invalid = ParseDict(
                {
                    "artifactId": "invalid",
                    "parts": [
                        {
                            "data": {"total": -1, "label": "secret"},
                            "mediaType": "application/json",
                            "metadata": {
                                EXTENSION_URI: {
                                    "role": "primary",
                                    "contractId": contract_id,
                                    "direction": "output",
                                    "representationId": output.representation.id,
                                }
                            },
                        }
                    ],
                },
                Artifact(),
            )
            await event_queue.enqueue_event(
                Task(
                    id=execution.task_id,
                    context_id=execution.context_id,
                    status={"state": "TASK_STATE_COMPLETED"},
                    artifacts=[invalid],
                )
            )
            return

        artifacts: list[Artifact] = []
        if output is not None and settings.get("omit") is not True:
            artifact = output_artifact(execution, value)
            if settings.get("companions") is True:
                artifact.parts.append(
                    Part(text="Invoice complete.", media_type="text/plain")
                )
                artifacts.append(artifact)
                artifacts.append(
                    ParseDict(
                        {
                            "artifactId": "audit-companion",
                            "parts": [
                                {
                                    "data": {"audit": True},
                                    "mediaType": "application/json",
                                }
                            ],
                        },
                        Artifact(),
                    )
                )
            else:
                artifacts.append(artifact)

        if settings.get("stream") is True:
            await event_queue.enqueue_event(
                Task(
                    id=execution.task_id,
                    context_id=execution.context_id,
                    status={"state": "TASK_STATE_WORKING"},
                )
            )
            await event_queue.enqueue_event(
                ParseDict(
                    {
                        "taskId": execution.task_id,
                        "contextId": execution.context_id,
                        "status": {"state": "TASK_STATE_WORKING"},
                    },
                    TaskStatusUpdateEvent(),
                )
            )
            for artifact in artifacts:
                await event_queue.enqueue_event(
                    ParseDict(
                        {
                            "taskId": execution.task_id,
                            "contextId": execution.context_id,
                            "artifact": MessageToDict(artifact),
                            "lastChunk": True,
                        },
                        TaskArtifactUpdateEvent(),
                    )
                )
            await event_queue.enqueue_event(
                ParseDict(
                    {
                        "taskId": execution.task_id,
                        "contextId": execution.context_id,
                        "status": {"state": "TASK_STATE_COMPLETED"},
                    },
                    TaskStatusUpdateEvent(),
                )
            )
        else:
            await event_queue.enqueue_event(
                Task(
                    id=execution.task_id,
                    context_id=execution.context_id,
                    status={"state": "TASK_STATE_COMPLETED"},
                    artifacts=artifacts,
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return


async def serve(
    catalog_path: Path,
    host: str,
    port: int,
    *,
    fixture_origin: str | None = None,
    fixture_ca: Path | None = None,
    fixture_pins: Path | None = None,
) -> None:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    resolver = None
    if fixture_origin is not None:
        if fixture_ca is None or fixture_pins is None:
            raise ValueError("External fixture requires both CA and integrity pins")
        # Test-only explicit trust of the loopback TLS fixture. Production hosts
        # must supply their own origin, address, credential and trust policies.
        fixture_url = urlsplit(fixture_origin)
        if (
            fixture_url.scheme != "https"
            or fixture_url.hostname != "127.0.0.1"
            or fixture_url.username is not None
            or fixture_url.password is not None
            or fixture_url.port is None
            or fixture_url.path
            or fixture_url.query
            or fixture_url.fragment
        ):
            raise ValueError("External fixture origin must use loopback HTTPS")
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        tls.load_verify_locations(cafile=str(fixture_ca))
        resolver = ContractResolver(
            tls=tls,
            allowed_origins=(fixture_origin,),
            allowed_addresses={"127.0.0.1": ("127.0.0.1",)},
            resource_integrity=json.loads(fixture_pins.read_text(encoding="utf-8")),
        )
        try:
            catalog = await resolver.resolve_catalog(catalog, origin="local")
        except BaseException:
            await resolver.close()
            raise
    listener = socket.socket()
    listener.bind((host, port))
    base = f"http://{host}:{listener.getsockname()[1]}"
    card = ParseDict(
        {
            "name": "Invoice and presence reference",
            "description": "Independent Python provider",
            "version": "1.0",
            "supportedInterfaces": [
                {
                    "url": base + "/a2a",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
            "capabilities": {"streaming": True},
            "defaultInputModes": ["application/json", "text/plain"],
            "defaultOutputModes": ["application/json", "text/plain"],
            "skills": [],
        },
        AgentCard(),
    )
    executor = ReferenceAgent(os.environ.get("REFERENCE_EVIDENCE") == "1")
    boundary = ContractServer(
        card=card, catalog=catalog, executor=executor, required=True
    )
    executor.boundary = boundary
    app = create_app(boundary)

    async def with_evidence(scope: Scope, receive: Receive, send: Send) -> None:
        if (
            executor.evidence_enabled
            and scope["type"] == "http"
            and scope["path"] == "/shutdown"
            and scope["method"] == "POST"
        ):
            await JSONResponse({"stopping": True})(scope, receive, send)
            server.should_exit = True
        elif (
            executor.evidence_enabled
            and scope["type"] == "http"
            and scope["path"] == "/evidence"
        ):
            response = JSONResponse(
                {"executions": len(executor.calls), "calls": executor.calls}
            )
            await response(scope, receive, send)
        else:
            await app(scope, receive, send)

    server = uvicorn.Server(
        uvicorn.Config(with_evidence, log_level="error", lifespan="on")
    )
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if serving.done():
                    await serving
                await asyncio.sleep(0.01)
        print(json.dumps({"type": "ready", "url": base}), flush=True)
        await serving
    finally:
        server.should_exit = True
        if not serving.done():
            await serving
        listener.close()
        await boundary.close()
        if resolver is not None:
            await resolver.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--fixture-origin")
    parser.add_argument("--fixture-ca", type=Path)
    parser.add_argument("--fixture-pins", type=Path)
    args = parser.parse_args()
    asyncio.run(
        serve(
            args.catalog,
            args.host,
            args.port,
            fixture_origin=args.fixture_origin,
            fixture_ca=args.fixture_ca,
            fixture_pins=args.fixture_pins,
        )
    )


if __name__ == "__main__":
    main()
