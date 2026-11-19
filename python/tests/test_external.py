"""Pinned HTTPS catalog resources through independent installed applications."""

import asyncio
import base64
import hashlib
import json
import os
import ssl
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import ContractError
from a2a_schema_contract.resolver import ContractResolver

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tls"
CONTRACT = "urn:reference:external-echo:1"


class ExternalTests(unittest.IsolatedAsyncioTestCase):
    async def test_external_transitive_pinned_resources(self):
        cert = FIXTURES / "cert.pem"
        key = FIXTURES / "key.pem"
        server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_tls.load_cert_chain(cert, key)
        client_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_tls.load_verify_locations(cafile=str(cert))
        documents = {}
        requested = []

        async def serve(reader, writer):
            try:
                headers = await reader.readuntil(b"\r\n\r\n")
                path = headers.split(b" ")[1].decode("ascii")
                requested.append(path)
                body = documents[path]
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/schema+json\r\n"
                    + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                    + body
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        listener = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_tls)
        origin = f"https://127.0.0.1:{listener.sockets[0].getsockname()[1]}"
        documents["/root.json"] = json.dumps(
            {"$ref": "types.json#/$defs/echo"}
        ).encode()
        documents["/types.json"] = json.dumps(
            {
                "$defs": {
                    "echo": {
                        "type": "object",
                        "required": ["text"],
                        "properties": {"text": {"type": "string"}},
                        "additionalProperties": False,
                    }
                }
            }
        ).encode()
        pins = {
            origin + path: {
                "algorithm": "sha-256",
                "value": base64.b64encode(hashlib.sha256(body).digest()).decode(),
            }
            for path, body in documents.items()
        }
        schema = {
            "dialect": "https://json-schema.org/draft/2020-12/schema",
            "mediaType": "application/schema+json",
            "uri": origin + "/root.json",
        }
        representation = {
            "id": "json",
            "mediaType": "application/json",
            "schema": schema,
        }
        catalog = {
            "contracts": [
                {
                    "id": CONTRACT,
                    "input": {
                        "presence": "required",
                        "representations": [representation],
                    },
                    "output": {
                        "presence": "required",
                        "representations": [representation],
                    },
                }
            ]
        }
        process = None
        url = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                (path / "catalog.json").write_text(
                    json.dumps(catalog), encoding="utf-8"
                )
                (path / "pins.json").write_text(json.dumps(pins), encoding="utf-8")
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "a2a_schema_contract_reference.server",
                    "--catalog",
                    str(path / "catalog.json"),
                    "--fixture-origin",
                    origin,
                    "--fixture-ca",
                    str(cert),
                    "--fixture-pins",
                    str(path / "pins.json"),
                    env={**os.environ, "REFERENCE_EVIDENCE": "1"},
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                line = await asyncio.wait_for(process.stdout.readline(), timeout=20)
                if not line:
                    raise RuntimeError((await process.stderr.read()).decode())
                url = json.loads(line)["url"]
                async with ContractResolver(
                    tls=client_tls,
                    allowed_origins=(origin,),
                    allowed_addresses={"127.0.0.1": ("127.0.0.1",)},
                    resource_integrity=pins,
                ) as resolver:
                    async with await ContractClient.discover(
                        url, resolver=resolver
                    ) as client:
                        view = client.catalog.schema(CONTRACT, "input", "json")
                        prepared_catalog = client.catalog
                        self.assertIsNotNone(view)
                        self.assertEqual(len(view.documents), 2)
                        result = await client.invoke(
                            client.prepare(CONTRACT, input={"text": "hello"})
                        )
                        self.assertEqual(result.payload.value, {"text": "hello"})
                    resolver.clear_cache()
                    self.assertTrue(
                        prepared_catalog.select(CONTRACT, "input", "json").validate(
                            {"text": "offline"}
                        )
                    )
                self.assertGreaterEqual(requested.count("/root.json"), 1)
                self.assertGreaterEqual(requested.count("/types.json"), 1)
                bad_pins = dict(pins)
                bad_pins[origin + "/root.json"] = {
                    "algorithm": "sha-256",
                    "value": base64.b64encode(bytes(32)).decode(),
                }
                async with ContractResolver(
                    tls=client_tls,
                    allowed_origins=(origin,),
                    allowed_addresses={"127.0.0.1": ("127.0.0.1",)},
                    resource_integrity=bad_pins,
                ) as resolver:
                    with self.assertRaises(ContractError):
                        await resolver.resolve_catalog(catalog, origin="local")
        finally:
            if process is not None and process.returncode is None:
                if url is not None:
                    async with httpx.AsyncClient(timeout=5) as http:
                        await http.post(url + "/shutdown")
                else:
                    process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    self.fail("provider did not shut down")
            listener.close()
            await listener.wait_closed()


if __name__ == "__main__":
    unittest.main()
