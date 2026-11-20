"""Cancel a live streaming invocation and verify no business output publishes."""

import asyncio
import json
import sys
from contextlib import aclosing

import httpx
from a2a_schema_contract.client import ContractClient


async def run(url):
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        before = (await http.get(url + "/evidence")).json()["executions"]
        async with await ContractClient.discover(url) as client:
            invocation = client.prepare(
                "urn:reference:invoice:1",
                input={"quantity": 3, "unitPrice": 7, "label": None},
                input_representation_id="json",
                allow_server_selection=True,
                metadata={"fault": "wait"},
            )
            async with aclosing(client.stream(invocation)) as stream:
                first = await anext(stream)
                first_data = first.event.value
                if first_data["kind"] != "task":
                    raise AssertionError("expected initial task")
                task_id = first_data["data"]["id"]
                canceled = (await client.cancel_task(task_id)).value
                if canceled["status"]["state"] != "TASK_STATE_CANCELED":
                    raise AssertionError("cancel did not return canceled task")
                events = [event async for event in stream]
                if not events or events[-1].result is None:
                    raise AssertionError("missing canceled terminal result")
                result = events[-1].result.response.value
                if result["status"]["state"] != "TASK_STATE_CANCELED" or result.get(
                    "artifacts"
                ):
                    raise AssertionError("cancellation published business output")
        after = (await http.get(url + "/evidence")).json()["executions"]
        if after != before + 1:
            raise AssertionError("unexpected execution count")
    print(json.dumps({"id": "explicit-cancel", "outcome": "PASS", "executions": 1}))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run(sys.argv[1]), timeout=15))
