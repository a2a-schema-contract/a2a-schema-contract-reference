# Python reference implementation

The initial Python client can run explicitly selected HTTP success scenarios from
the shared manifest against a running reference agent. Install a built Python SDK
wheel and this project into the same environment:

```sh
python -m pip install '/path/to/a2a_schema_contract-0.1.0.dev0-py3-none-any.whl[server]' .
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
test-only `REFERENCE_EVIDENCE=1` flag, `/evidence` reports execution counts,
`POST /shutdown` requests graceful shutdown, and request metadata selects test behavior.
Do not expose this test mode or use the unauthenticated reference server for
production traffic. SIGINT or SIGTERM shuts down the provider.

Run the provider's admission and publication controls after installing the SDK
wheel and this package:

```sh
python -m unittest discover -s tests -v
```

These checks exercise real loopback HTTP, invalid wire input and output, four
dishonest peer responses with a valid control, and verified loopback TLS with
integrity-pinned transitive schemas, offline use and a wrong-pin refusal. The
`--fixture-origin`, `--fixture-ca` and `--fixture-pins` provider options are
explicitly restricted to this loopback test fixture, not production trust policy.

On macOS arm64, five test methods passed in separate noneditable wheel consumers
on CPython 3.11.15, 3.12.13, 3.13.14 and 3.14.10. The SDK wheel SHA-256 was
`950d5830ddcb92ed525580df9b426754957284ca23b45a48f4cbfaf080ba07ab` and
reference wheel SHA-256 was
`d5a347d533382986e710bf356709e3ecd169c82fe6939c94603ed55c2a8ad613`.
These checks do not establish the full cross-platform or interoperability profile;
REF-005/006 remain incomplete.

For a clean consumer outside the checkout, build the SDK and reference wheels,
then run the following from the repository root with `uv` on the path:

```sh
python python/scripts/check_installed.py \
  --sdk-wheel /path/to/a2a_schema_contract-0.1.0.dev0-py3-none-any.whl \
  --reference-wheel python/dist/a2a_schema_contract_reference-0.1.0.dev0-py3-none-any.whl
```

The script checks the SDK hash recorded in `python/artifact-input.json`, installs
both wheels in a fresh temporary environment, copies only tests and fixtures,
and reports wheel hashes and the interpreter. The configured GitHub workflow
rebuilds the pinned SDK source and runs this check across Linux, macOS and Windows;
the configuration alone is not evidence of a hosted pass.
