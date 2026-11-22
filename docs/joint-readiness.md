# Joint reference readiness

This repository and the SDK are development previews. A source checkout or a
passing focused workflow does not constitute a registry release or production
support commitment.

| Component        | Artifact intake                                                            | Verified scope and limits                                                                                                                                                                             |
| ---------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Node reference   | `js/artifact-input.json`: SDK `0.1.0-rc.1`, exact revision and SHA-256     | Node 22.23.3 and 24.21.0; installed consumers and independent scenarios. Prior reports retain their original artifact hash.                                                                           |
| Python reference | `python/artifact-input.json`: SDK `0.1.0.dev0`, exact revision and SHA-256 | CPython 3.11–3.14; the hosted consumer matrix includes Linux 3.11–3.14 and macOS/Windows 3.14. The SDK wheel is built once on Linux and verified before installation on each runner.                  |
| Contract         | `contract-source.json` pins specification revision `a5c0075`               | The pinned draft is authoritative; examples do not expand its normative scope.                                                                                                                        |
| Joint profiles   | `interoperability/README.md`                                               | Four-pairing profiles run from built artifacts. The complete inline manifest is not a pass while root-null behavior differs; external, adversarial and platform coverage must be assessed separately. |

The [Node quickstart](../README.md#node-quickstart) and
[Python quickstart](../README.md#python-quickstart) build the reviewed SDK source
and install independent consumers. `python/scripts/check_installed.py` verifies
the SDK hash and creates a temporary consumer; `js/scripts/clean-check.mjs`
performs the corresponding Node gate. Their builds need access to package
dependencies. Local-artifact intake avoids a published SDK registry package but
is not, by itself, a fully offline dependency installation.

The [Python hosted matrix](https://github.com/a2a-schema-contract/a2a-schema-contract-reference/actions/runs/44661315021)
passed at reference `70fbbe4` with the pinned Python SDK wheel; the
[Node candidate matrix](https://github.com/a2a-schema-contract/a2a-schema-contract-reference/actions/runs/44661314796)
passed at that same reference revision with its then-current Node SDK pin.
Subsequent artifact-pin changes require fresh checks; consult current run results
and do not reuse old receipts for new bytes. The latest generated parity workflow
must be evaluated against the full acceptance requirements, not only its focused
success cases.

The replacement Node pin `3b91182783d0789926b96d3ef926398780f1b7eafa36bf82ead674d58923aa15`
was rebuilt from SDK `e3b2e9bf0718e47b6cf9b33493a3b947b06f9096` in a fresh
checkout on macOS arm64 Node 24.21.0. Its source `npm ci` reported zero known
vulnerabilities, the reference hash-verified install succeeded, and the isolated
`npm run check:clean` gate passed. The earlier pin remains recorded in historical
reports. Both artifacts use the private `0.1.0-rc.1` development version but have
different bytes; use the hash and source revision, not the version alone, to
identify them. Fresh hosted reference validation and parity against this new pin are
required before treating the replacement as jointly accepted. A fresh Python
quickstart consumer on CPython 3.12.13 passed eight tests and two real loopback
calls; a point-in-time dependency audit found no known vulnerabilities, excluding
the two unpublished local packages that the audit service could not identify.

Before a joint release, complete REF-005/006, decide the root-null support and
cross-language profile, validate all supported tutorials and operations flows,
record the final artifact hashes and OS/runtime evidence, and complete SDK-012
and REF-008. Recheck dependency audits at release time and document unresolved
findings. Registry name ownership, provenance, release tags, publication and
maintenance policy are separate release steps. Security reports go through the
[private reporting policy](../SECURITY.md).
