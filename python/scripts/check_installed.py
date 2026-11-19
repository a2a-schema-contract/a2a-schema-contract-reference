"""Verify and exercise built wheels from a fresh consumer outside the checkout."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REFERENCE_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-wheel", type=Path, required=True)
    parser.add_argument("--reference-wheel", type=Path, required=True)
    args = parser.parse_args()
    sdk_wheel, reference_wheel = (
        args.sdk_wheel.resolve(),
        args.reference_wheel.resolve(),
    )
    pin = json.loads((REFERENCE_ROOT / "python/artifact-input.json").read_text())
    digest = hashlib.sha256(sdk_wheel.read_bytes()).hexdigest()
    if digest != pin["sdkWheelSha256"]:
        raise ValueError(f"SDK wheel SHA-256 mismatch: {digest}")
    with tempfile.TemporaryDirectory(prefix="a2a-reference-consumer-") as temp:
        consumer = Path(temp)
        subprocess.run(
            [sys.executable, "-m", "venv", str(consumer / "venv")], check=True
        )
        python = (
            consumer
            / "venv"
            / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                str(sdk_wheel),
                str(reference_wheel),
            ],
            check=True,
            cwd=consumer,
        )
        shutil.copytree(REFERENCE_ROOT / "python/tests", consumer / "python/tests")
        shutil.copytree(REFERENCE_ROOT / "fixtures", consumer / "fixtures")
        subprocess.run(
            [str(python), "-m", "unittest", "discover", "-s", "python/tests", "-v"],
            cwd=consumer,
            check=True,
            timeout=180,
        )
        print(
            json.dumps(
                {
                    "sdkRevision": pin["sdkRevision"],
                    "sdkWheelSha256": digest,
                    "referenceWheelSha256": hashlib.sha256(
                        reference_wheel.read_bytes()
                    ).hexdigest(),
                    "python": sys.version,
                    "result": "PASS",
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
