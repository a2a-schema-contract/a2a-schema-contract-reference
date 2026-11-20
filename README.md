# A2A Schema Contract Reference Applications

Runnable **A2A (Agent2Agent) clients and agents** demonstrating Schema Contract
discovery, JSON Schema input/output validation, representation negotiation and
HTTP/SSE exchanges. The applications install the
[A2A Schema Contract SDK](https://github.com/shashikanth-gs/a2a-schema-contract-sdk)
as built npm and Python artifacts and use its public APIs.

The invoice agent advertises a versioned catalog in its Agent Card. A client
learns the schema at runtime, constructs a request, selects the contract and
representation, activates the extension, and validates the result. Deterministic
scenarios make the behavior reproducible without a model provider or cloud
credentials.

**Node release candidate:** the applications cover **37 inline scenarios**
and **43 independent protocol/security scenarios**, plus **28 flight-discovery
checks** in embedded/external variants against a hash-pinned SDK
artifact. A Python provider and client and four-pairing interoperability checks
are in progress on `codex/python-reference`. The full inline parity manifest has
an unresolved root-null carrier difference; broader joint release gates remain
open. Package releases are not published. The community specification remains authoritative:
[A2A Schema Contract](https://github.com/shashikanth-gs/a2a-schema-contract).

## What the examples demonstrate

- Discovery of an unfamiliar agent's input/output schemas and explicit contract activation.
- All nine required/optional/absent input-output combinations.
- JSON/text alternatives, representation negotiation and companion Parts.
- Empty values and nested JSON null, with explicit unsupported-carrier refusal.
- Task and Message results, bounded atomic SSE results and INPUT_REQUIRED continuation.
- Plain JavaScript and compiled TypeScript clients consuming the installed SDK.
- Skill-associated discovery, immutable schema resources and compact explicit invocation.

The reference imports public package paths and keeps its own expected results.
Application execution does not depend on an SDK source checkout or workspace
schema files.

## Node quickstart

Use Node **22 >=22.23.3** or **24 >=24.21.0**, npm and ESM. The reference currently
accepts the unscoped Node release candidate. Build that exact revision so the
artifact matches the committed SHA-256 pin.

From a directory where you want both checkouts:

```sh
git clone https://github.com/shashikanth-gs/a2a-schema-contract-sdk.git
git -C a2a-schema-contract-sdk checkout --detach e3b2e9bf0718e47b6cf9b33493a3b947b06f9096
cd a2a-schema-contract-sdk/js
npm ci
npm run build
mkdir -p artifacts
npm pack --ignore-scripts --pack-destination artifacts
cd ../..
export SDK_ARTIFACT="$PWD/a2a-schema-contract-sdk/js/artifacts/a2a-schema-contract-0.1.0-rc.1.tgz"
git clone --branch codex/python-reference https://github.com/shashikanth-gs/a2a-schema-contract-reference.git
cd a2a-schema-contract-reference/js
npm run artifact:install
npm run scenarios
npm run discovery
```

`artifact:install` verifies the tarball before installing dependencies. The runner
starts an agent on a dynamic loopback port, executes the 37 scenarios and shuts
down its processes. Expected summary:

```json
{ "result": "PASS", "scenarios": 37, "node": "v22.23.3" }
```

The `node` field reflects the supported runtime you use. Run one scenario with
`npm run scenarios -- --scenario invoice-json-discovery`. The
[Node quickstart](js/README.md) covers separate agent/client processes and all
commands. SDK source is used only to produce the initial artifact; the installed
reference runs independently thereafter.

## Python quickstart

This preview requires CPython 3.11–3.14 and `uv`. From a fresh directory:

```sh
git clone https://github.com/shashikanth-gs/a2a-schema-contract-sdk.git
git -C a2a-schema-contract-sdk checkout --detach e3b2e9bf0718e47b6cf9b33493a3b947b06f9096
cd a2a-schema-contract-sdk/python
uv build --wheel
cd ../..
git clone --branch codex/python-reference https://github.com/shashikanth-gs/a2a-schema-contract-reference.git
cd a2a-schema-contract-reference
uv venv --python 3.12 python/.venv
uv pip install --python python/.venv/bin/python ../a2a-schema-contract-sdk/python/dist/a2a_schema_contract-0.1.0.dev0-py3-none-any.whl ./python
python/.venv/bin/python -m unittest discover -s python/tests -v
REFERENCE_EVIDENCE=1 python/.venv/bin/python -m a2a_schema_contract_reference.server --catalog fixtures/catalog.json
```

The last command prints a readiness JSON record with a loopback URL. In a second
terminal, from the reference repository, substitute that URL:

```sh
python/.venv/bin/python -m a2a_schema_contract_reference.client http://127.0.0.1:PORT --manifest fixtures/scenarios.json --scenario invoice-json-discovery --scenario invoice-compact-selection
```

Both scenarios should report `PASS`. Stop the server with Ctrl-C. Evidence mode
enables testing endpoints and must not be exposed to untrusted clients. These
commands use Unix shell paths; see the [Python guide](python/README.md) for
artifact checks and operating limits.

## Documentation

| Guide                                                                            | What it covers                                                                    |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| [Node quickstart](js/README.md)                                                  | Artifact intake, agent/client commands and local execution                        |
| [Python quickstart](python/README.md)                                            | Pinned wheel consumers, reference agent and security checks                       |
| [Interoperability](interoperability/README.md)                                   | Four-pairing profiles, reproducibility and open gaps                              |
| [Joint readiness](docs/joint-readiness.md)                                       | Compatibility, artifact intake and remaining release gates                        |
| [Changelog](CHANGELOG.md)                                                        | Unreleased reference changes and their status                                     |
| [Flight-discovery tutorial](docs/discovery-tutorial.md)                          | Skill associations, original schema resources and compact invocation              |
| [Developer-experience validation](docs/developer-experience-report.md)           | RC1 artifact pin and installed JS/TS acceptance                                   |
| [Wire-flow tutorial](docs/inline-tutorial.md)                                    | Discovery, schema construction, activation, validation and scenario behavior      |
| [Inline checkpoint report](docs/inline-reference-report.md)                      | Exact artifact/revision pins, test evidence and supported limits                  |
| [Candidate validation](docs/node-candidate-report.md)                            | Source/checksum pins, independent security scenarios and actual hosted matrix     |
| [Operations guide](docs/node-operations.md)                                      | Readiness, shutdown, limits, authentication/context ownership and troubleshooting |
| [Scenario manifest](fixtures/scenarios.json)                                     | Independent expected outcomes for the 37 scenarios                                |
| [SDK implementation](https://github.com/shashikanth-gs/a2a-schema-contract-sdk)  | Reusable core, client/server adapters and HTTPS resolver                          |
| [Community specification](https://github.com/shashikanth-gs/a2a-schema-contract) | Normative draft and extension schemas                                             |
| [Roadmap](PLAN.md)                                                               | Reference deliverables and remaining coverage                                     |

The pinned artifact version, SHA-256 and SDK revision are in
[js/artifact-input.json](js/artifact-input.json). This reference checkpoint uses
SDK commit `e3b2e9bf0718e47b6cf9b33493a3b947b06f9096`, including secure external
resolution and isolated async schema validation. A new artifact requires reviewed
pin updates and fresh consumer validation.

## Validate and contribute

After `artifact:install`, from `js/`:

```sh
npm run check
npm run security
npm run check:clean
```

Candidate validation uses fresh installed consumers on Node 22.23.3 and
24.21.0. The [candidate workflow](.github/workflows/node-candidate.yml) also
checks Linux Node 22/24 and macOS/Windows Node 24, building the exact SDK revision
and verifying the artifact pin. The manual artifact workflow remains available.
The [operations guide](docs/node-operations.md) covers deployment and diagnostics;
final run evidence is recorded in the candidate report and PLAN.md.

See [CONTRIBUTING.md](CONTRIBUTING.md) for scenario and artifact changes and
[SECURITY.md](SECURITY.md) for private vulnerability reporting. Use
[issues](https://github.com/shashikanth-gs/a2a-schema-contract-reference/issues)
for bugs and feature requests, and
[discussions](https://github.com/shashikanth-gs/a2a-schema-contract-reference/discussions)
for questions about the examples.

## Repository layout

| Directory           | Contents                                                                     |
| ------------------- | ---------------------------------------------------------------------------- |
| `js/`               | TypeScript agent, JavaScript/TypeScript clients and isolated artifact checks |
| `fixtures/`         | Versioned invoice catalog and language-neutral scenario expectations         |
| `docs/`             | Tutorial and reproducible validation evidence                                |
| `python/`           | Python client, provider, artifact intake and independent security checks     |
| `interoperability/` | Four-pairing harness and retained reports                                    |

Licensed under [Apache-2.0](LICENSE).
