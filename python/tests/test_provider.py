"""Installed-consumer provider checks; no SDK source imports or internet required."""

import asyncio
import copy
import json
import os
import signal
import sys
import unittest
from pathlib import Path

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import EXTENSION_URI

CATALOG = Path(__file__).resolve().parents[2] / "fixtures" / "catalog.json"
CONTRACT = "urn:reference:invoice:1"
INVOICE = {"quantity": 3, "unitPrice": 7, "label": None}


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "a2a_schema_contract_reference.server",
            "--catalog",
            str(CATALOG),
            env={**os.environ, "REFERENCE_EVIDENCE": "1"},
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
        await self.http.aclose()
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=10)
        except TimeoutError:
            self.process.kill()
            await self.process.wait()
            self.fail("provider did not shut down")
        # Uvicorn completes lifespan shutdown, then re-raises the captured signal.
        self.assertIn(self.process.returncode, (0, -signal.SIGTERM))

    def prepare(self, **kwargs):
        return self.client.prepare(
            CONTRACT,
            input=INVOICE,
            input_representation_id="json",
            accepted_output_representation_ids=["rich"],
            **kwargs,
        )

    async def test_invalid_wire_input_never_executes(self):
        request = copy.deepcopy(self.prepare().request.value)
        request["message"]["parts"][0]["data"]["quantity"] = -1
        response = await self.http.post(
            self.url + "/a2a",
            headers={"A2A-Extensions": EXTENSION_URI, "A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "invalid",
                "method": "SendMessage",
                "params": request,
            },
        )
        self.assertIn("error", response.json())
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


if __name__ == "__main__":
    unittest.main()
