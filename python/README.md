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

The runner chooses the expected output representation explicitly if the manifest
omits that choice. Python currently requires a choice when several representations
are available; this does not test Node's implicit selection behavior. Streaming,
continuation, expected failures, server-side execution evidence and a Python agent
are not implemented in this initial runner. REF-005/006 remain incomplete.
