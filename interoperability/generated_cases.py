"""Generate deterministic invoice boundary cases from independent invariants."""

import argparse
import json
from pathlib import Path


def generate():
    cases = []

    def invoice(case_id, value, expected):
        cases.append(
            {
                "id": case_id,
                "invocation": {
                    "contractId": "urn:reference:invoice:1",
                    "input": {"representationId": "json", "value": value},
                    "acceptedOutputRepresentationIds": ["rich"],
                },
                "expected": expected,
            }
        )

    # Expected arithmetic and admission rules are specified here, not obtained
    # by calling either implementation under test.
    for quantity, price, label in [
        (0, 0, None),
        (1, 100, ""),
        (100, 100, "x"),
        (7, 13, None),
    ]:
        invoice(
            f"generated-valid-{quantity}-{price}",
            {"quantity": quantity, "unitPrice": price, "label": label},
            {
                "present": True,
                "value": {"total": quantity * price, "label": label},
                "representationId": "rich",
            },
        )
    for name, quantity in [
        ("below", -1),
        ("above", 101),
        ("boolean", True),
        ("fraction", 1.5),
        ("string", "1"),
        ("null", None),
    ]:
        invoice(
            f"generated-invalid-quantity-{name}",
            {"quantity": quantity, "unitPrice": 1, "label": None},
            {"localError": "INSTANCE_INVALID", "executions": 0},
        )
    for name, value in [
        ("missing-label", {"quantity": 1, "unitPrice": 1}),
        (
            "extra-property",
            {"quantity": 1, "unitPrice": 1, "label": None, "extra": True},
        ),
        ("invalid-label", {"quantity": 1, "unitPrice": 1, "label": False}),
    ]:
        invoice(
            f"generated-{name}",
            value,
            {"localError": "INSTANCE_INVALID", "executions": 0},
        )
    for name, text in [("letters", "a1"), ("too-long", "12345"), ("minus", "-1")]:
        cases.append(
            {
                "id": f"generated-text-{name}",
                "invocation": {
                    "contractId": "urn:reference:invoice:1",
                    "input": {"representationId": "text", "value": text},
                    "acceptedOutputRepresentationIds": ["rich"],
                },
                "expected": {"localError": "INSTANCE_INVALID", "executions": 0},
            }
        )
    return {
        "formatVersion": 1,
        "profile": "generated-invoice-boundaries-v1",
        "extensionUri": "https://w3id.org/a2a-schema-contract/draft/0.1",
        "scenarios": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(generate(), indent=2) + "\n")
