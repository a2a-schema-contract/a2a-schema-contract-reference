"""Run generated parity in a copied, noneditable artifact consumer."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-wheel", required=True, type=Path)
    parser.add_argument("--reference-wheel", required=True, type=Path)
    parser.add_argument("--node-artifact", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--cancellation-report", type=Path)
    parser.add_argument("--discovery-report", type=Path)
    parser.add_argument("--dishonest-report", type=Path)
    args = parser.parse_args()
    sdk, reference, tarball, node, report = (
        path.resolve()
        for path in (
            args.sdk_wheel,
            args.reference_wheel,
            args.node_artifact,
            args.node,
            args.report,
        )
    )
    with tempfile.TemporaryDirectory(prefix="a2a-parity-consumer-") as name:
        consumer = Path(name)
        # Snapshot inputs so concurrent builds cannot change bytes under this run.
        sdk_copy = consumer / sdk.name
        reference_copy = consumer / reference.name
        tarball_copy = consumer / tarball.name
        for source, target in (
            (sdk, sdk_copy),
            (reference, reference_copy),
            (tarball, tarball_copy),
        ):
            shutil.copyfile(source, target)
        sdk, reference, tarball = sdk_copy, reference_copy, tarball_copy
        for directory in ("fixtures", "interoperability", "js"):
            shutil.copytree(
                ROOT / directory,
                consumer / directory,
                ignore=shutil.ignore_patterns(
                    "node_modules", "dist", "artifacts", "reports", "__pycache__"
                ),
            )
        subprocess.run(
            [sys.executable, "-m", "venv", str(consumer / "venv")], check=True
        )
        python = (
            consumer
            / "venv"
            / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        )
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("PYTHONPATH", "PYTHONHOME")
        }
        env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(sdk), str(reference)],
            cwd=consumer,
            env=env,
            check=True,
            timeout=180,
        )
        env["SDK_ARTIFACT"] = str(tarball)
        subprocess.run(
            ["npm", "run", "artifact:install"],
            cwd=consumer / "js",
            env=env,
            check=True,
            timeout=180,
        )
        subprocess.run(
            ["npm", "run", "build"],
            cwd=consumer / "js",
            env=env,
            check=True,
            timeout=180,
        )
        manifest = consumer / "generated.json"
        subprocess.run(
            [
                str(python),
                "interoperability/generated_cases.py",
                "--output",
                str(manifest),
            ],
            cwd=consumer,
            env=env,
            check=True,
            timeout=30,
        )
        # The clean reference copy is the harness root; SDK source trees are absent.
        with tempfile.TemporaryDirectory(prefix="a2a-parity-isolated-") as isolated:
            base = [
                str(python),
                "interoperability/run.py",
                "--python",
                str(python),
                "--node",
                str(node),
                "--python-wheel",
                str(sdk),
                "--node-artifact",
                str(tarball),
                "--isolated-cwd",
                isolated,
            ]
            reports = [(report, ["--manifest", str(manifest)])]
            if args.cancellation_report:
                reports.append((args.cancellation_report.resolve(), ["--cancellation"]))
            if args.discovery_report:
                reports.append((args.discovery_report.resolve(), ["--discovery"]))
            if args.dishonest_report:
                reports.append((args.dishonest_report.resolve(), ["--dishonest"]))
            failed = False
            for output, options in reports:
                completed = subprocess.run(
                    [*base, *options, "--report", str(output)],
                    cwd=consumer,
                    env=env,
                    check=False,
                    timeout=600,
                )
                if completed.returncode:
                    failed = True
                if not output.is_file():
                    raise RuntimeError(
                        f"Parity runner did not produce a report: {output}"
                    )
        results = [json.loads(output.read_text()) for output, _ in reports]
        installed = Path(results[0]["python_imports"][1]).parent.resolve()
        with zipfile.ZipFile(reference) as wheel:
            files = [
                name
                for name in wheel.namelist()
                if name.startswith("a2a_schema_contract_reference/")
                and not name.endswith("/")
            ]
            if not files:
                raise RuntimeError("Reference wheel contains no package files")
            for name in files:
                target = (
                    installed / Path(name).relative_to("a2a_schema_contract_reference")
                ).resolve()
                if (
                    installed not in target.parents
                    or not target.is_file()
                    or target.read_bytes() != wheel.read(name)
                ):
                    raise RuntimeError(
                        f"Installed reference differs from wheel: {name}"
                    )
        for (output, _), result in zip(reports, results, strict=True):
            result.pop("python_imports", None)
            result["reference_wheel_sha256"] = hashlib.sha256(
                reference.read_bytes()
            ).hexdigest()
            output.write_text(json.dumps(result, indent=2) + "\n")
        if failed:
            raise RuntimeError(
                "One or more parity profiles failed; inspect retained reports"
            )


if __name__ == "__main__":
    main()
