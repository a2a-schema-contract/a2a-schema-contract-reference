# Python reference implementation

The Python client runs selected scenarios from the shared manifest against a
running reference agent in evidence mode. Install a built Python SDK
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

The provider owns a loopback listener, SDK validation workers and its in-memory
task store. Start it in a separate process and use the URL from its readiness
record; the default port is selected by the OS. It drains and closes SDK state
on shutdown. Tests use `POST /shutdown` only with evidence mode enabled. The
fixture server does not provide authentication, authorization, durable task
storage or production monitoring; a host must supply those capabilities.
Its invoice business function uses application-owned `TypedDict` input and output
types after the SDK validates the original wire payload against the shared schema.

If discovery fails, check the readiness URL and confirm the Python SDK wheel is
installed with the `server` extra. External-resource fixture failures should be
checked against the exact trusted origin, fixture CA and resource integrity pins;
an arbitrary loopback address or an unpinned document is refused. A canceled
local client operation does not itself request remote task cancellation; use the
SDK's explicit cancellation operation when that behavior is required.

Run the provider's admission and publication controls after installing the SDK
wheel and this package:

```sh
python -m unittest discover -s tests -v
```

These checks exercise real loopback HTTP, invalid wire input and output, nine
dishonest peer responses and invalid or truncated streams with valid controls,
and verified loopback TLS with integrity-pinned transitive schemas, offline use
and a wrong-pin refusal. The
`--fixture-origin`, `--fixture-ca` and `--fixture-pins` provider options are
explicitly restricted to this loopback test fixture, not production trust policy.

On macOS arm64, five test methods passed in separate noneditable wheel consumers
on CPython 3.11.15, 3.12.13, 3.13.14 and 3.14.10. The SDK wheel SHA-256 was
`950d5830ddcb92ed525580df9b426754957284ca23b45a48f4cbfaf080ba07ab` and
reference wheel SHA-256 was
`d5a347d533382986e710bf356709e3ecd169c82fe6939c94603ed55c2a8ad613`.
The expanded seven-method security and discovery suite passed locally on CPython
3.12.13 with SDK wheel
`de1458954cdf61b5c05272901820aaeb22e8451081c196e475851cef8bef2579` and
reference wheel
`584d1b45a99fe0d889fe3d59f2239a68f9e47a295de7ccb6cb65222ed49a44ba`.
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
and reports wheel hashes and the interpreter. The configured GitHub workflow builds
the pinned SDK source once on Linux and checks the same wheel on Linux, macOS and
Windows. Platform builds contain identical files but do not have identical ZIP
bytes, so this does not claim reproducible cross-platform wheel hashes. The workflow
also checks formatting, lint and strict types for application modules and the
installed-consumer script; tests are not included in the strict type check. The
configuration alone is not evidence of a hosted pass.
