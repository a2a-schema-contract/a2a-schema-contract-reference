"""Verify pinned transitive HTTPS schemas across an installed Python client."""

import asyncio
import base64
import json
import ssl
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import ContractError
from a2a_schema_contract.resolver import ContractResolver


async def run(url, origin, ca_path, pins_path):
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls.load_verify_locations(cafile=ca_path)
    hostname = urlsplit(origin).hostname
    pins = json.loads(Path(pins_path).read_text())

    async def lookup(name):
        if name != hostname:
            raise ValueError("Unexpected fixture hostname")
        return ("127.0.0.1",)

    async with ContractResolver(
        tls=tls,
        allowed_origins=(origin,),
        allowed_addresses={hostname: ("127.0.0.1",)},
        lookup=lookup,
        resource_integrity=pins,
    ) as resolver:
        async with await ContractClient.discover(url, resolver=resolver) as client:
            identifier = "urn:reference:external-echo:1"
            schema = client.catalog.schema(identifier, "input", "json")
            if schema is None or len(schema.documents) != 2:
                raise AssertionError("expected both transitive schema resources")
            result = await client.invoke(
                client.prepare(identifier, input={"text": "external fixture"})
            )
            if (
                result.payload is None
                or not result.payload.present
                or result.payload.value != {"text": "external fixture"}
            ):
                raise AssertionError("unexpected external-schema result")
            prepared = client.catalog
        resolver.clear_cache()
        if not prepared.select(identifier, "input", "json").validate(
            {"text": "offline"}
        ):
            raise AssertionError("prepared resources failed offline validation")
    async with httpx.AsyncClient(timeout=5, trust_env=False) as evidence:
        before = (await evidence.get(url + "/evidence")).json()["executions"]
    bad_pins = {
        **pins,
        origin + "/types.json": {
            "algorithm": "sha-256",
            "value": base64.b64encode(bytes(32)).decode(),
        },
    }
    async with ContractResolver(
        tls=tls,
        allowed_origins=(origin,),
        allowed_addresses={hostname: ("127.0.0.1",)},
        lookup=lookup,
        resource_integrity=bad_pins,
    ) as bad_resolver:
        try:
            await ContractClient.discover(url, resolver=bad_resolver)
        except ContractError as error:
            if error.code != "INTEGRITY_MISMATCH":
                raise
        else:
            raise AssertionError("bad transitive integrity was not rejected")
    async with httpx.AsyncClient(timeout=5, trust_env=False) as evidence:
        if (await evidence.get(url + "/evidence")).json()["executions"] != before:
            raise AssertionError("bad integrity unexpectedly dispatched business work")
    print(json.dumps({"id": "external-transitive", "outcome": "PASS"}))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(*sys.argv[1:]), timeout=25))
