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
records their hashes along with the manifest, catalog and import paths. It does not
yet provide independent
external-resource, cancellation, malformed-peer, generated-case, and discovery
coverage. It also does not yet establish a supported OS/runtime matrix. Thus a
passing inline manifest alone is not REF-006 acceptance. See the reference plan
for the complete gate.

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

These reports describe a local development artifact, not a release gate: the
interpreter/OS matrix and the external-resource, cancellation, adversarial,
discovery and clean-consumer checks listed above remain outstanding. Server
shutdown on Windows also needs a verified graceful-control path.
