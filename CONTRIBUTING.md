# Contributing

Use the [Node quickstart](js/README.md) to install the hash-pinned SDK artifact,
then run `npm run check` and `npm run check:clean` from `js/` on a supported Node
22 or 24 runtime. See the [roadmap](PLAN.md) and
[validation report](docs/inline-reference-report.md) before changing supported
behavior.

Keep the reference independent of SDK internals. Application code imports public
installed-package paths. Domain catalogs and expected scenario outcomes belong
in `fixtures/`; assertions should establish behavior, values, execution timing
and cleanup. Normative extension changes belong in the
[specification repository](https://github.com/shashikanth-gs/a2a-schema-contract).
Reusable validation changes belong in the
[SDK repository](https://github.com/shashikanth-gs/a2a-schema-contract-sdk).

Use `npm run format` for formatting. Follow the committed lockfile and keep the
artifact's version, source revision and SHA-256 in `js/artifact-input.json` aligned.
An SDK artifact update needs new consumer evidence; changing a hash alone does
not establish compatibility. Record the exact commands, runtime, scenario
results and remaining limitations in the owning task/report.

For Python changes, follow the [Python quickstart](README.md#python-quickstart),
run `python/.venv/bin/python -m unittest discover -s python/tests -v` from the
repository root, and run `python/scripts/check_installed.py` with the SDK and
reference wheels as described in the [Python guide](python/README.md). The
script verifies the committed SDK wheel hash before creating an isolated
consumer. Changes to the pinned revision or wheel bytes require independent
installed-consumer evidence and a corresponding update to
`python/artifact-input.json` and the Python workflow. CI checks Python source
formatting, lint and strict application types.

Run the appropriate [interoperability profiles](interoperability/README.md)
when changing client/server semantics. A selected subset reports `PARTIAL`; do
not treat it as full four-pairing acceptance. Retain specific artifact hashes,
scenario outcomes and known differences, including root-null carrier behavior.

Open an issue describing the scenario or bug, with a small reproduction and
expected behavior. Keep example data synthetic and omit credentials/private
payloads. Send security findings through [SECURITY.md](SECURITY.md). Package
publication and broader release work remain separate from repository changes.
