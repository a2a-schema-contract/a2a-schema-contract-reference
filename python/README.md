# Python reference implementation

The initial Python client can run explicitly selected HTTP success scenarios from
the shared manifest against a running reference agent. Install a built Python SDK
wheel with its `a2a` extra, then install this project into the same environment:

```sh
python -m pip install '/path/to/a2a_schema_contract-0.1.0.dev0-py3-none-any.whl[a2a]' .
python -m a2a_schema_contract_reference.client http://127.0.0.1:PORT \
  --manifest ../fixtures/scenarios.json --scenario invoice-json-discovery \
  --scenario invoice-compact-selection
```

Start the Python provider with the same shared catalog:

```sh
REFERENCE_EVIDENCE=1 python -m a2a_schema_contract_reference.server \
  --catalog ../fixtures/catalog.json
```

It prints a JSON readiness record containing its loopback URL. With the explicit
test-only `REFERENCE_EVIDENCE=1` flag, `/evidence` reports execution counts and
metadata used by the scenarios, and request metadata can select test behavior.
Do not expose this test mode or use the unauthenticated reference server for
production traffic. SIGINT or SIGTERM shuts down the provider.

Run the provider's admission and publication controls after installing the SDK
wheel and this package:

```sh
python -m unittest discover -s tests -v
```

These tests exercise real loopback HTTP with an invalid wire input, deliberately
invalid provider output and a valid control. They do not establish the full
cross-platform or interoperability profile. Python requires an explicit output
choice when discovery offers alternatives; whether that differs from the Node
profile is being assessed by REF-006. REF-005/006 remain incomplete.

The initial local checks used CPython 3.12.13 on macOS arm64 and a noneditable
SDK `0.1.0.dev0` wheel with SHA-256
`98bfa08660e814215c8e343fc67d05e91c62e96607d01854bfe9ecacce1a2f22`.
Other supported SDK interpreters and platforms have not yet been verified here.
