"""Run selected shared scenarios against an independently hosted agent."""

import argparse
import asyncio
import json
from pathlib import Path

from a2a_schema_contract.client import ContractClient


async def run(url: str, manifest: Path, selected: list[str]) -> None:
    scenarios = json.loads(manifest.read_text(encoding="utf-8"))["scenarios"]
    by_id = {scenario["id"]: scenario for scenario in scenarios}
    for scenario_id in selected:
        if scenario_id not in by_id:
            raise ValueError(f"Unknown scenario: {scenario_id}")
    async with await ContractClient.discover(url) as client:
        for scenario_id in selected:
            scenario = by_id[scenario_id]
            invocation = scenario["invocation"]
            if scenario.get("transport") or scenario["expected"].get("localError"):
                raise ValueError(f"Scenario not yet supported by this runner: {scenario_id}")
            kwargs = {}
            if "input" in invocation:
                kwargs["input"] = invocation["input"]["value"]
                kwargs["input_representation_id"] = invocation["input"]["representationId"]
            if "acceptedOutputRepresentationIds" in invocation:
                kwargs["accepted_output_representation_ids"] = invocation["acceptedOutputRepresentationIds"]
            elif scenario["expected"].get("representationId"):
                # Python requires an explicit choice when discovery offers alternatives.
                kwargs["accepted_output_representation_ids"] = [scenario["expected"]["representationId"]]
            for source, target in (("metadata", "metadata"), ("companions", "companions")):
                if source in invocation:
                    kwargs[target] = invocation[source]
            if "configuration" in invocation:
                kwargs["accepted_output_modes"] = invocation["configuration"]["acceptedOutputModes"]
            result = await client.invoke(client.prepare(invocation["contractId"], **kwargs))
            expected = scenario["expected"]
            if result.payload is None or result.payload.present != expected["present"]:
                raise AssertionError(f"{scenario_id}: unexpected payload presence")
            if expected["present"]:
                if result.payload.value != expected["value"]:
                    raise AssertionError(f"{scenario_id}: unexpected payload value")
                if result.payload.representation_id != expected["representationId"]:
                    raise AssertionError(f"{scenario_id}: unexpected representation")
            print(f"PASS {scenario_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--scenario", action="append", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.manifest, args.scenario))


if __name__ == "__main__":
    main()
