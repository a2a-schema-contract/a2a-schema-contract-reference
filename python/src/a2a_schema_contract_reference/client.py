"""Execute a shared reference scenario through the installed Python SDK."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from a2a_schema_contract.client import ContractClient
from a2a_schema_contract.core import EXTENSION_URI, ContractError


async def run(url: str, scenario: dict, explicit_default: bool = False) -> dict:
    invocation, expected = scenario["invocation"], scenario["expected"]
    kwargs = {}
    if "input" in invocation:
        kwargs["input"] = invocation["input"]["value"]
        kwargs["input_representation_id"] = invocation["input"]["representationId"]
    if "acceptedOutputRepresentationIds" in invocation:
        kwargs["accepted_output_representation_ids"] = invocation[
            "acceptedOutputRepresentationIds"
        ]
    elif explicit_default and expected.get("representationId"):
        # Diagnostic mode only: the unmodified manifest otherwise tests selection parity.
        kwargs["accepted_output_representation_ids"] = [expected["representationId"]]
    else:
        # Match the manifest's omitted wire field: the server selects an offered output.
        kwargs["allow_server_selection"] = True
    for source in ("metadata", "companions"):
        if source in invocation:
            kwargs[source] = invocation[source]
    if "configuration" in invocation:
        kwargs["accepted_output_modes"] = invocation["configuration"][
            "acceptedOutputModes"
        ]
    async with httpx.AsyncClient(timeout=5, trust_env=False) as evidence_client:
        before = (await evidence_client.get(url + "/evidence")).json()["executions"]
        async with await ContractClient.discover(url) as client:
            try:
                prepared = client.prepare(invocation["contractId"], **kwargs)
                if scenario.get("transport") == "sse":
                    events = [event async for event in client.stream(prepared)]
                    results = [
                        event.result for event in events if event.result is not None
                    ]
                    if len(results) != 1 or events[-1].result is None:
                        raise AssertionError(
                            "stream must contain exactly one final result"
                        )
                    result = results[0]
                elif scenario.get("transport") == "continuation":
                    first = await client.invoke(prepared)
                    initial = first.response.value
                    if (
                        initial["status"]["state"] != "TASK_STATE_INPUT_REQUIRED"
                        or first.payload is not None
                    ):
                        raise AssertionError("expected input-required task")
                    kwargs["metadata"] = {}
                    kwargs["task_id"] = initial["id"]
                    kwargs["context_id"] = initial["contextId"]
                    result = await client.invoke(
                        client.prepare(invocation["contractId"], **kwargs)
                    )
                    if (
                        result.response.value["id"],
                        result.response.value["contextId"],
                    ) != (initial["id"], initial["contextId"]):
                        raise AssertionError("continuation changed task identity")
                else:
                    result = await client.invoke(prepared)
            except ContractError as error:
                if error.code != expected.get("localError"):
                    raise
                after = (await evidence_client.get(url + "/evidence")).json()[
                    "executions"
                ]
                if after != before:
                    raise AssertionError("invalid input reached the executor")
                return {
                    "id": scenario["id"],
                    "outcome": "PASS",
                    "diagnostic": error.code,
                    "executions": 0,
                }
            if "localError" in expected:
                raise AssertionError("expected local refusal")
            payload = result.payload
            if payload is None or payload.present != expected["present"]:
                raise AssertionError("unexpected payload presence")
            response = result.response.value
            metadata = response.get("metadata", {}).get(EXTENSION_URI, {})
            if metadata.get("contractId") != invocation["contractId"]:
                raise AssertionError("result contract identity mismatch")
            if payload.present:
                if (
                    payload.value != expected["value"]
                    or payload.representation_id != expected["representationId"]
                ):
                    raise AssertionError("unexpected payload value or representation")
                if metadata.get("outputRepresentationId") != payload.representation_id:
                    raise AssertionError("result representation identity mismatch")
                if payload.part.value.get("metadata", {}).get(EXTENSION_URI) != {
                    "contractId": invocation["contractId"],
                    "direction": "output",
                    "representationId": payload.representation_id,
                    "role": "primary",
                }:
                    raise AssertionError("primary part identity mismatch")
            elif "outputRepresentationId" in metadata:
                raise AssertionError("absent output has a representation identity")
            if expected.get("carrier") == "message":
                if "parts" not in response:
                    raise AssertionError("expected standalone message")
            elif response.get("status", {}).get("state") != "TASK_STATE_COMPLETED":
                raise AssertionError("expected completed task")
            after = (await evidence_client.get(url + "/evidence")).json()
            if after["executions"] - before != expected.get("executions", 1):
                raise AssertionError("unexpected executor count")
            call = after["calls"][-1]
            if call["inputPresent"] != expected.get(
                "inputPresent", "input" in invocation
            ):
                raise AssertionError("unexpected executor input presence")
            if (
                "inputPartCount" in expected
                and call["inputPartCount"] != expected["inputPartCount"]
            ):
                raise AssertionError("unexpected input part count")
            if (
                "artifactCount" in expected
                and len(response.get("artifacts", [])) != expected["artifactCount"]
            ):
                raise AssertionError("unexpected artifact count")
            return {
                "id": scenario["id"],
                "outcome": "PASS",
                "present": payload.present,
                "representationId": payload.representation_id
                if payload.present
                else None,
                "executions": after["executions"] - before,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scenario", action="append", required=True)
    parser.add_argument("--explicit-default", action="store_true")
    args = parser.parse_args()
    by_id = {
        item["id"]: item for item in json.loads(args.manifest.read_text())["scenarios"]
    }
    for scenario_id in args.scenario:
        print(
            json.dumps(
                asyncio.run(run(args.url, by_id[scenario_id], args.explicit_default))
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
