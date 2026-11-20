# Interoperability validation

`run.py` runs the shared `fixtures/scenarios.json` manifest with Node and Python
clients against fresh Node and Python servers, covering all four pairings. Each
scenario is a separate client process. The clients compare results and execution
counters with the manifest; failures and stderr are retained in a JSON report.
The Python client deliberately asks the SDK to leave output selection to the
server when the fixture omits an accepted-output list. This preserves the wire
request rather than deriving a choice from the expected result.

Prepare a supported Node runtime and the installed Node artifact/compiled
reference described in `js/README.md`. Install a built Python SDK wheel with the
`server` extra and a built reference wheel into an isolated Python environment;
the SDK wheel must include `allow_server_selection`. Run from the repository:

```sh
python interoperability/run.py --python /absolute/path/to/venv/bin/python \
  --node /absolute/path/to/node --python-wheel /absolute/path/to/sdk.whl \
  --node-artifact /absolute/path/to/sdk.tgz --isolated-cwd /absolute/path/to/empty-directory \
  --report /absolute/path/to/report.json
```

The working directory must be outside the reference checkout. `PYTHONPATH` and
`PYTHONHOME` are removed and Python package imports must resolve from
`site-packages`. Each server is stopped even on a failure. A full manifest run
reports `PASS` only if every scenario in every pairing passes; `--scenario ID`
may be repeated for a subset and reports `PARTIAL` on success. An optional
`--explicit-default` mode makes an output choice from the manifest's expected
result for diagnosis and can never produce a full `PASS`.

The runner compares installed SDK package files with the supplied artifacts and
records their hashes along with the manifest, catalog and import paths. A passing
inline manifest alone is not REF-006 acceptance. See the reference plan for the
complete gate.

`generated_cases.py --output /tmp/generated.json` produces 16 deterministic
valid/invalid invoice boundary cases. Run them in every pairing using
`--manifest /tmp/generated.json`; `--cancellation` and `--discovery` select
independent explicit-cancel and embedded skill/schema-discovery profiles. The
cancel profile verifies an initial task, an explicit cancellation, a canceled
terminal event and no output; discovery checks association, schema inspection,
invalid-input zero dispatch and flight invocation. These focused profiles do not
cover all security and interoperability requirements.

`check_clean.py` copies the reference into a temporary consumer, installs supplied
SDK and reference wheels and the Node tarball, verifies installed package bytes,
and runs generated cases. `--cancellation-report` and `--discovery-report` add the
other profiles. The generated-parity GitHub workflow configures these checks for
Linux Node 22/24 with Python 3.12; check actual workflow results before claiming
hosted coverage. The three local reports from November 20 record successful runs
of these profiles with Node 24.21.0 and Python 3.12.13, SDK `e3b2e9b` and reference
wheel SHA-256 `108855d6b223b88a7806ec6fe2e0ce82c3bd89824db642e904e20bf9b0918da8`.

The existing `root-null-refused` fixture reflects the Node 1.3.0 carrier's
inability to represent root JSON null. Python's SDK accepts root null, so the
same expectation is not valid for both clients. The full unmodified manifest
currently reports this difference as a failure; it is not a shared-profile
pass, and the failure must not be omitted from a parity claim.

The retained macOS arm64 CPython 3.12.13 runs on Node 22.23.3 and 24.21.0 are
in [reports](reports/). Both ran all 37 manifest scenarios in all four pairings
against SDK source `208a3ca` and reference source `14866cc`. Node→Node and
Node→Python passed 37 each; Python→Node and Python→Python passed 36 each. For
`root-null-refused`, Node clients refuse locally as the fixture expects; the
Python client represents root null. Against the Node server the request is
rejected at the carrier boundary; against the Python server the request succeeds.
That difference is outside the shared carrier profile and remains a reported
failure in these full-manifest reports. The reports omit local absolute import
paths and error traces; they retain individual outcomes and verified SDK hashes.

These reports describe a local development artifact, not a release gate: broader
interpreter/OS coverage and four-pairing external-resource, malformed-peer,
disconnect cancellation, generated-case breadth and external discovery checks
remain outstanding. Server shutdown on Windows also needs a verified
graceful-control path.
