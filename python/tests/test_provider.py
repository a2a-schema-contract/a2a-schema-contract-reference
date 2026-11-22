"""Installed-consumer provider checks; no SDK source imports or internet required."""

import asyncio
import copy
import json
import os
import sys
import unittest
from pathlib import Path

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import EXTENSION_URI, ContractError

CATALOG = Path(__file__).resolve().parents[2] / "fixtures" / "catalog.json"
CONTRACT = "urn:reference:invoice:1"
INVOICE = {"quantity": 3, "unitPrice": 7, "label": None}
SKILLS = [
    {
        "id": "invoice",
        "name": "Invoice",
        "description": "Invoice fixture",
        "tags": ["test"],
    }
]


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "a2a_schema_contract_reference.server",
            "--catalog",
            str(CATALOG),
            env={
                **os.environ,
                "REFERENCE_EVIDENCE": "1",
                "REFERENCE_SKILLS_JSON": json.dumps(SKILLS),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=10)
        if not line:
            raise RuntimeError((await self.process.stderr.read()).decode())
        self.url = json.loads(line)["url"]
        self.client = await ContractClient.discover(self.url)
        self.http = httpx.AsyncClient(timeout=10)

    async def asyncTearDown(self):
        await self.client.close()
        await self.http.post(self.url + "/shutdown")
        await self.http.aclose()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=10)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
            self.fail("provider did not shut down")
        self.assertEqual(self.process.returncode, 0)

    def prepare(self, **kwargs):
        return self.client.prepare(
            CONTRACT,
            input=INVOICE,
            input_representation_id="json",
            accepted_output_representation_ids=["rich"],
            **kwargs,
        )

    async def test_invalid_wire_input_never_executes(self):
        for mutation in (
            "invalid-value",
            "wrong-media",
            "missing-primary",
            "unknown-representation",
        ):
            request = copy.deepcopy(self.prepare().request.value)
            part = request["message"]["parts"][0]
            if mutation == "invalid-value":
                part["data"]["quantity"] = -1
            elif mutation == "wrong-media":
                part["mediaType"] = "text/plain"
            elif mutation == "missing-primary":
                del part["metadata"]
            elif mutation == "unknown-representation":
                request["metadata"][EXTENSION_URI]["inputRepresentationId"] = "unknown"
            response = await self.http.post(
                self.url + "/a2a",
                headers={"A2A-Extensions": EXTENSION_URI, "A2A-Version": "1.0"},
                json={
                    "jsonrpc": "2.0",
                    "id": mutation,
                    "method": "SendMessage",
                    "params": request,
                },
            )
            self.assertIn("error", response.json(), mutation)
        evidence = (await self.http.get(self.url + "/evidence")).json()
        self.assertEqual(evidence["executions"], 0)

    async def test_invalid_output_is_not_published(self):
        result = await self.client.invoke(self.prepare(metadata={"fault": "invalid"}))
        wire = result.response.value
        self.assertEqual(wire["status"]["state"], "TASK_STATE_FAILED")
        self.assertFalse(wire.get("artifacts"))
        self.assertNotIn("secret", json.dumps(wire))
        self.assertEqual(
            (await self.http.get(self.url + "/evidence")).json()["executions"], 1
        )

    async def test_valid_control(self):
        result = await self.client.invoke(self.prepare())
        self.assertTrue(result.payload.present)
        self.assertEqual(result.payload.value, {"total": 21, "label": None})

    async def test_evidence_skill_is_advertised(self):
        card = (await self.http.get(self.url + "/.well-known/agent-card.json")).json()
        self.assertEqual(card["skills"][0]["id"], "invoice")

    async def test_evidence_routes_and_skills_are_disabled_by_default(self):
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "a2a_schema_contract_reference.server",
            "--catalog",
            str(CATALOG),
            env={
                **{
                    key: value
                    for key, value in os.environ.items()
                    if key != "REFERENCE_EVIDENCE"
                },
                "REFERENCE_SKILLS_JSON": json.dumps(SKILLS),
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
            if not line:
                raise RuntimeError((await process.stderr.read()).decode())
            url = json.loads(line)["url"]
            self.assertEqual((await self.http.get(url + "/evidence")).status_code, 404)
            self.assertEqual((await self.http.post(url + "/shutdown")).status_code, 404)
            card = (await self.http.get(url + "/.well-known/agent-card.json")).json()
            self.assertFalse(card.get("skills"))
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    self.fail("provider did not exit after termination")

    async def test_external_catalog_fixture_requires_evidence(self):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "a2a_schema_contract_reference.server", "--catalog", str(CATALOG),
            "--fixture-origin", "https://127.0.0.1:443",
            "--fixture-catalog-reference", "https://127.0.0.1:443/catalog.json",
            env={key: value for key, value in os.environ.items() if key != "REFERENCE_EVIDENCE"},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertNotIn(b'"type": "ready"', stdout)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def test_dishonest_peer_cannot_publish_invalid_result(self):
        # Reuse the actual agent's card, but independently construct the JSON-RPC
        # response a dishonest peer might send. The client must validate wire data.
        card = (await self.http.get(self.url + "/.well-known/agent-card.json")).json()
        for mutation in (
            "valid",
            "invalid-value",
            "wrong-contract",
            "missing-primary",
            "bad-json",
            "wrong-media",
            "wrong-echo",
            "duplicate-primary",
            "unknown-state",
            "foreign-task",
        ):
            marker = {
                "role": "primary",
                "contractId": CONTRACT,
                "direction": "output",
                "representationId": "rich",
            }
            part = {
                "data": {"total": 21, "label": None},
                "mediaType": "application/json",
                "metadata": {EXTENSION_URI: marker},
            }
            if mutation == "invalid-value":
                part["data"]["total"] = -1
            elif mutation == "wrong-contract":
                marker["contractId"] = "urn:other:1"
            elif mutation == "missing-primary":
                del part["metadata"]
            elif mutation == "wrong-media":
                part["mediaType"] = "text/plain"
            task = {
                "id": "task",
                "contextId": "context",
                "status": {"state": "TASK_STATE_COMPLETED"},
                "metadata": {
                    EXTENSION_URI: {
                        "contractId": CONTRACT,
                        "outputRepresentationId": "rich",
                    }
                },
                "artifacts": [{"artifactId": "output", "parts": [part]}],
            }
            if mutation == "wrong-echo":
                task["metadata"][EXTENSION_URI]["outputRepresentationId"] = "other"
            elif mutation == "duplicate-primary":
                task["artifacts"][0]["parts"].append(copy.deepcopy(part))
            elif mutation == "unknown-state":
                task["status"]["state"] = "TASK_STATE_UNKNOWN_VALUE"
            elif mutation == "foreign-task":
                task["id"] = "foreign"

            def reply(request, mutation=mutation, task=task):
                if request.method == "GET":
                    return httpx.Response(200, json=card)
                if mutation == "bad-json":
                    return httpx.Response(200, content=b'{"jsonrpc":')
                wire = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": wire["id"], "result": {"task": task}},
                )

            async with (
                httpx.AsyncClient(transport=httpx.MockTransport(reply)) as fake_http,
                await ContractClient.discover(
                    self.url, http_client=fake_http
                ) as client,
            ):
                invocation = client.prepare(
                    CONTRACT,
                    input=INVOICE,
                    input_representation_id="json",
                    accepted_output_representation_ids=["rich"],
                    task_id="task",
                    context_id="context",
                )
                if mutation == "valid":
                    result = await client.invoke(invocation)
                    self.assertEqual(result.payload.value, {"total": 21, "label": None})
                else:
                    with self.assertRaises(ContractError, msg=mutation):
                        await client.invoke(invocation)

    async def test_dishonest_stream_never_exposes_partial_business_output(self):
        card = (await self.http.get(self.url + "/.well-known/agent-card.json")).json()
        for mutation in ("valid", "invalid-value", "truncated"):
            part = {
                "data": {
                    "total": -1 if mutation == "invalid-value" else 21,
                    "label": None,
                },
                "mediaType": "application/json",
                "metadata": {
                    EXTENSION_URI: {
                        "role": "primary",
                        "contractId": CONTRACT,
                        "direction": "output",
                        "representationId": "rich",
                    }
                },
            }
            events = [
                {
                    "task": {
                        "id": "task",
                        "contextId": "context",
                        "status": {"state": "TASK_STATE_WORKING"},
                    }
                },
                {
                    "artifactUpdate": {
                        "taskId": "task",
                        "contextId": "context",
                        "lastChunk": True,
                        "artifact": {"artifactId": "output", "parts": [part]},
                    }
                },
                {
                    "statusUpdate": {
                        "taskId": "task",
                        "contextId": "context",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                        "metadata": {
                            EXTENSION_URI: {
                                "contractId": CONTRACT,
                                "outputRepresentationId": "rich",
                            }
                        },
                    }
                },
            ]

            def reply(request, mutation=mutation, events=events):
                if request.method == "GET":
                    return httpx.Response(200, json=card)
                wire = json.loads(request.content)
                selected = events[:-1] if mutation == "truncated" else events
                body = "".join(
                    "data: "
                    + json.dumps({"jsonrpc": "2.0", "id": wire["id"], "result": event})
                    + "\n\n"
                    for event in selected
                )
                return httpx.Response(
                    200, headers={"content-type": "text/event-stream"}, content=body
                )

            async with (
                httpx.AsyncClient(transport=httpx.MockTransport(reply)) as fake_http,
                await ContractClient.discover(
                    self.url, http_client=fake_http
                ) as client,
            ):
                invocation = client.prepare(
                    CONTRACT,
                    input=INVOICE,
                    input_representation_id="json",
                    accepted_output_representation_ids=["rich"],
                )
                published = []
                if mutation == "valid":
                    published = [event async for event in client.stream(invocation)]
                    self.assertEqual(
                        published[-1].result.payload.value, {"total": 21, "label": None}
                    )
                else:
                    with self.assertRaises(ContractError, msg=mutation):
                        async for event in client.stream(invocation):
                            published.append(event)
                    self.assertTrue(all(event.result is None for event in published))


if __name__ == "__main__":
    unittest.main()
