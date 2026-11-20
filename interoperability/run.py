"""Run explicit shared scenarios in all four installed-client/server pairings."""

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "fixtures/scenarios.json"
CATALOG = ROOT / "fixtures/catalog.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    scenarios = (
        ["explicit-cancel"]
        if args.cancellation
        else ["skill-discovery"]
        if args.discovery
        else ["dishonest-output"]
        if args.dishonest
        else ["external-transitive"]
        if args.external_config
        else [item["id"] for item in manifest["scenarios"]]
    )
    catalog_path = ROOT / "fixtures/flight-catalog.json" if args.discovery else CATALOG
    selected = args.scenario or scenarios
    if len(set(selected)) != len(selected) or any(
        item not in scenarios for item in selected
    ):
        raise ValueError("Scenario names must be known and unique")
    report = {
        "profile": (
            "explicit-cancellation-v1"
            if args.cancellation
            else "inline-skill-discovery-v1"
            if args.discovery
            else "dishonest-output-v1"
            if args.dishonest
            else "external-transitive-v1"
            if args.external_config
            else manifest["profile"]
        ),
        "manifest_sha256": digest(manifest_path),
        "catalog_sha256": digest(catalog_path),
        "pairings": [],
    }
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME")
    }
    probe = subprocess.run(
        [
            args.python,
            "-c",
            (
                "import json,a2a_schema_contract,a2a_schema_contract_reference; "
                "print(json.dumps([a2a_schema_contract.__file__,a2a_schema_contract_reference.__file__]))"
            ),
        ],
        cwd=args.isolated_cwd,
        env=clean_env,
        capture_output=True,
        text=True,
        check=True,
    )
    imports = json.loads(probe.stdout)
    if any("site-packages" not in Path(path).resolve().parts for path in imports):
        raise RuntimeError(
            "Python imports resolved to reference source rather than installed artifacts"
        )
    report["python_imports"] = imports
    report["python_version"] = subprocess.run(
        [args.python, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    report["node_version"] = subprocess.run(
        [args.node, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    installed_python = Path(imports[0]).parent.resolve()
    with zipfile.ZipFile(args.python_wheel) as wheel:
        files = [
            name
            for name in wheel.namelist()
            if name.startswith("a2a_schema_contract/") and not name.endswith("/")
        ]
        if not files:
            raise RuntimeError("SDK wheel contains no package files")
        for name in files:
            target = (
                installed_python / Path(name).relative_to("a2a_schema_contract")
            ).resolve()
            if (
                installed_python not in target.parents
                or not target.is_file()
                or target.read_bytes() != wheel.read(name)
            ):
                raise RuntimeError(f"Installed Python SDK differs from wheel: {name}")
    installed_node = (ROOT / "js/node_modules/a2a-schema-contract").resolve()
    with tarfile.open(args.node_artifact, "r:gz") as archive:
        files = [item for item in archive.getmembers() if item.isfile()]
        if not files:
            raise RuntimeError("Node SDK artifact is empty")
        for item in files:
            target = (installed_node / Path(item.name).relative_to("package")).resolve()
            if (
                installed_node not in target.parents
                or not target.is_file()
                or target.read_bytes() != archive.extractfile(item).read()
            ):
                raise RuntimeError(
                    f"Installed Node SDK differs from tarball: {item.name}"
                )
    report["python_sdk_wheel_sha256"] = digest(args.python_wheel)
    report["node_sdk_tarball_sha256"] = digest(args.node_artifact)
    external = (
        json.loads(args.external_config.read_text()) if args.external_config else None
    )
    if external:
        report["external_catalog_sha256"] = {
            side: digest(Path(external[side]["catalog"])) for side in ("node", "python")
        }
    for server in ("node", "python"):
        for client in ("node", "python"):
            command = (
                [args.node, str(ROOT / "js/dist/server/main.js")]
                if server == "node"
                else [
                    args.python,
                    "-m",
                    "a2a_schema_contract_reference.server",
                    "--catalog",
                    str(
                        Path(external[server]["catalog"]) if external else catalog_path
                    ),
                ]
            )
            if external and server == "python":
                config = external[server]
                command.extend(
                    [
                        "--fixture-origin",
                        config["origin"],
                        "--fixture-ca",
                        config["ca"],
                        "--fixture-pins",
                        config["pins"],
                    ]
                )
            env = {**clean_env, "REFERENCE_EVIDENCE": "1", "REFERENCE_PORT": "0"}
            if external and server == "node":
                config = external[server]
                env["REFERENCE_CATALOG_JSON"] = Path(config["catalog"]).read_text()
                env["REFERENCE_RESOLVER_ORIGIN"] = config["origin"]
                env["REFERENCE_RESOLVER_PINS_JSON"] = Path(config["pins"]).read_text()
            if args.discovery:
                env["REFERENCE_CATALOG_JSON"] = catalog_path.read_text()
                env["REFERENCE_SKILLS_JSON"] = (
                    ROOT / "interoperability/discovery-skills.json"
                ).read_text()
            stderr = tempfile.TemporaryFile(mode="w+t")  # noqa: SIM115 - closed in finally
            process = subprocess.Popen(
                command,
                cwd=args.isolated_cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
            )
            pairing = {"client": client, "server": server, "scenarios": []}
            report["pairings"].append(pairing)
            try:
                lines = queue.Queue()
                threading.Thread(
                    target=lambda out=process.stdout, target=lines: target.put(
                        out.readline()
                    ),
                    daemon=True,
                ).start()
                try:
                    line = lines.get(timeout=args.timeout)
                except queue.Empty as exc:
                    raise TimeoutError("server readiness timeout") from exc
                ready = json.loads(line)
                if ready.get("type") != "ready" or not ready.get("url", "").startswith(
                    "http://127.0.0.1:"
                ):
                    raise RuntimeError(f"invalid readiness message: {ready!r}")
                for scenario in selected:
                    if args.cancellation and client == "node":
                        call = [
                            args.node,
                            str(ROOT / "js/src/client/cancel-parity.mjs"),
                            ready["url"],
                        ]
                    elif args.cancellation:
                        call = [
                            args.python,
                            str(ROOT / "interoperability/cancel_python.py"),
                            ready["url"],
                        ]
                    elif args.discovery and client == "node":
                        call = [
                            args.node,
                            str(ROOT / "js/src/client/discovery-parity.mjs"),
                            ready["url"],
                        ]
                    elif args.discovery:
                        call = [
                            args.python,
                            str(ROOT / "interoperability/discovery_python.py"),
                            ready["url"],
                        ]
                    elif args.dishonest and client == "node":
                        call = [
                            args.node,
                            str(ROOT / "js/src/client/dishonest-parity.mjs"),
                            ready["url"],
                        ]
                    elif args.dishonest:
                        call = [
                            args.python,
                            str(ROOT / "interoperability/dishonest_python.py"),
                            ready["url"],
                        ]
                    elif external:
                        config = external[server]
                        script = (
                            ROOT / "js/src/client/external-parity.mjs"
                            if client == "node"
                            else ROOT / "interoperability/external_python.py"
                        )
                        call = [
                            args.node if client == "node" else args.python,
                            str(script),
                            ready["url"],
                            config["origin"],
                            config["ca"],
                            config["pins"],
                        ]
                    elif client == "node":
                        call = [
                            args.node,
                            str(ROOT / "interoperability/node-client.mjs"),
                            ready["url"],
                            scenario,
                            str(manifest_path),
                        ]
                    else:
                        call = [
                            args.python,
                            "-m",
                            "a2a_schema_contract_reference.client",
                            ready["url"],
                            "--manifest",
                            str(manifest_path),
                            "--scenario",
                            scenario,
                        ]
                        if args.explicit_default:
                            call.append("--explicit-default")
                    try:
                        result = subprocess.run(
                            call,
                            cwd=args.isolated_cwd,
                            env=clean_env,
                            capture_output=True,
                            text=True,
                            timeout=args.timeout,
                            check=True,
                        )
                        outcome = json.loads(result.stdout.strip().splitlines()[-1])
                    except (subprocess.SubprocessError, ValueError, IndexError) as exc:
                        outcome = {"id": scenario, "outcome": "FAIL", "error": str(exc)}
                        if isinstance(exc, subprocess.CalledProcessError):
                            outcome["stderr"] = exc.stderr[:2000] + exc.stderr[-2000:]
                    pairing["scenarios"].append(outcome)
                    print(
                        f"{client} -> {server} {scenario}: {outcome['outcome']}",
                        flush=True,
                    )
            except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
                pairing["error"] = str(exc)
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                if "error" in pairing:
                    stderr.seek(0)
                    pairing["stderr"] = stderr.read()[-4000:]
                stderr.close()
    report["diagnostic_explicit_default"] = args.explicit_default
    report["complete_manifest"] = selected == scenarios
    passed = len(report["pairings"]) == 4 and all(
        "error" not in pairing
        and len(pairing["scenarios"]) == len(selected)
        and all(case["outcome"] == "PASS" for case in pairing["scenarios"])
        for pairing in report["pairings"]
    )
    report["result"] = (
        "FAIL"
        if not passed
        else "PASS"
        if report["complete_manifest"] and not args.explicit_default
        else "PARTIAL"
    )
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['result']}: {args.report}")
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        required=True,
        help="Absolute path to isolated Python with installed artifacts",
    )
    parser.add_argument(
        "--node", required=True, help="Absolute path to supported Node runtime"
    )
    parser.add_argument(
        "--python-wheel", type=Path, required=True, help="Installed SDK wheel"
    )
    parser.add_argument(
        "--node-artifact", type=Path, required=True, help="Installed SDK tarball"
    )
    parser.add_argument(
        "--isolated-cwd",
        type=Path,
        required=True,
        help="Empty directory outside the source checkout",
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        "--cancellation", action="store_true", help="Run explicit cancellation profile"
    )
    profiles.add_argument(
        "--discovery", action="store_true", help="Run embedded skill discovery profile"
    )
    profiles.add_argument(
        "--dishonest", action="store_true", help="Run dishonest-output profile"
    )
    profiles.add_argument(
        "--external-config", type=Path, help="Run loopback external-schema profile"
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="Repeat to run an explicit subset; default is complete manifest",
    )
    parser.add_argument(
        "--explicit-default",
        action="store_true",
        help="Diagnostic only: make Python output selection explicit",
    )
    parser.add_argument("--timeout", type=float, default=30)
    options = parser.parse_args()
    if not Path(options.python).is_absolute() or not Path(options.node).is_absolute():
        parser.error("Python and Node must be absolute executable paths")
    if (
        not options.isolated_cwd.is_dir()
        or ROOT in options.isolated_cwd.resolve().parents
    ):
        parser.error("isolated-cwd must exist outside the source checkout")
    sys.exit(0 if run(options) else 1)
