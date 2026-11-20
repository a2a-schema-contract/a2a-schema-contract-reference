"""Verify skill associations, original schema inspection and invocation."""

import asyncio
import json
import sys

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import ContractError


async def run(url):
    identifier = "urn:reference:flight-search:1"
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:  # noqa: SIM117
        async with await ContractClient.discover(url) as client:
            description = client.describe()
            assert [len(item.contracts) for item in description.skills] == [4, 2, 0]
            assert len(description.unassociated) == 1
            assert description.stale_associations == (
                ("urn:reference:flight-search:5", "missing-skill"),
            )
            assert (
                description.skills[0].contracts[3].input[0].diagnostic
                == "UNSUPPORTED_MEDIA_TYPE"
            )
            assert client.bind_skill("flight-search", identifier).id == identifier
            schema = client.catalog.schema(identifier, "input", "json")
            assert schema is not None
            assert schema.documents[0].value["required"] == ["origin", "destination"]
            before = (await http.get(url + "/evidence")).json()["executions"]
            try:
                client.prepare(identifier, input={"origin": "BLR"})
            except ContractError as error:
                assert error.code == "INSTANCE_INVALID"
            else:
                raise AssertionError("invalid input was not rejected")
            assert (await http.get(url + "/evidence")).json()["executions"] == before
            result = await client.invoke(
                client.prepare(
                    identifier, input={"origin": "BLR", "destination": "DEL"}
                )
            )
            assert result.payload is not None and result.payload.present
            assert result.payload.value == {
                "flights": [
                    {"flightNumber": "REF101", "origin": "BLR", "destination": "DEL"}
                ]
            }
    print(json.dumps({"id": "skill-discovery", "outcome": "PASS"}))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(sys.argv[1]), timeout=20))
