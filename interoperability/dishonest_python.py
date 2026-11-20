"""Ensure a client rejects a schema-invalid result from a dishonest peer."""

import asyncio
import json
import sys

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import ContractError


class TamperTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.upstream = httpx.AsyncHTTPTransport()
        self.mutated = False

    async def handle_async_request(self, request):
        response = await self.upstream.handle_async_request(request)
        if request.method != "POST":
            return response
        try:
            body = json.loads(await response.aread())
            part = body["result"]["task"]["artifacts"][0]["parts"][0]
            part["data"] = {"total": -1, "label": None}
            self.mutated = True
            return httpx.Response(response.status_code, json=body, request=request)
        finally:
            await response.aclose()

    async def aclose(self):
        await self.upstream.aclose()


async def run(url):
    transport = TamperTransport()
    async with httpx.AsyncClient(timeout=10, trust_env=False) as evidence:
        before = (await evidence.get(url + "/evidence")).json()["executions"]
        async with httpx.AsyncClient(  # noqa: SIM117
            transport=transport, timeout=10, trust_env=False
        ) as http:
            async with await ContractClient.discover(url, http_client=http) as client:
                prepared = client.prepare(
                    "urn:reference:invoice:1",
                    input={"quantity": 3, "unitPrice": 7, "label": None},
                    input_representation_id="json",
                    accepted_output_representation_ids=["rich"],
                )
                try:
                    await client.invoke(prepared)
                except ContractError as error:
                    if error.code != "INSTANCE_INVALID":
                        raise
                else:
                    raise AssertionError("dishonest result was not rejected")
        if not transport.mutated:
            raise AssertionError("test did not mutate a successful response")
        after = (await evidence.get(url + "/evidence")).json()["executions"]
        if after != before + 1:
            raise AssertionError("unexpected executor count")
    print(json.dumps({"id": "dishonest-output", "outcome": "PASS", "executions": 1}))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(sys.argv[1]), timeout=20))
