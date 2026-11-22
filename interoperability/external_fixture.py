"""Serve deterministic pinned transitive schemas and run four pairings."""

import argparse
import base64
import hashlib
import json
import ssl
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERT = ROOT / "fixtures/tls/cert.pem"
KEY = ROOT / "fixtures/tls/key.pem"


def pin(value):
    return {
        "algorithm": "sha-256",
        "value": base64.b64encode(hashlib.sha256(value).digest()).decode(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True)
    parser.add_argument("--node", required=True)
    parser.add_argument("--python-wheel", required=True)
    parser.add_argument("--node-artifact", required=True)
    parser.add_argument("--isolated-cwd", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    docs = {
        "/root.json": json.dumps({"$ref": "types.json#/$defs/echo"}).encode(),
        "/types.json": json.dumps(
            {
                "$defs": {
                    "echo": {
                        "type": "object",
                        "required": ["text"],
                        "properties": {"text": {"type": "string"}},
                        "additionalProperties": False,
                    }
                }
            }
        ).encode(),
    }
    base_catalog = json.loads((ROOT / "fixtures/flight-catalog.json").read_text())
    input_schema = base_catalog["contracts"][0]["input"]["representations"][0][
        "schema"
    ]["inline"]
    output_schema = base_catalog["contracts"][0]["output"]["representations"][0][
        "schema"
    ]["inline"]
    docs["/flight-input.json"] = json.dumps(input_schema).encode()
    docs["/flight-output.json"] = json.dumps(output_schema).encode()
    catalogs = {}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            hostname = self.headers.get("Host", "").split(":", 1)[0]
            body = (
                catalogs.get(hostname)
                if self.path == "/catalog.json"
                else docs.get(self.path)
            )
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "application/json"
                if self.path == "/catalog.json"
                else "application/schema+json",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT, KEY)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix="a2a-external-config-") as temp:
            directory = Path(temp)
            configurations = {}
            for side, hostname in (("node", "catalog.test"), ("python", "127.0.0.1")):
                origin = f"https://{hostname}:{server.server_port}"
                pins = {origin + path: pin(body) for path, body in docs.items()}
                schema = {
                    "dialect": "https://json-schema.org/draft/2020-12/schema",
                    "mediaType": "application/schema+json",
                    "uri": origin + "/root.json",
                    "integrity": pins[origin + "/root.json"],
                }
                representation = {
                    "id": "json",
                    "mediaType": "application/json",
                    "schema": schema,
                }
                catalog = json.loads(json.dumps(base_catalog))
                for contract in catalog["contracts"]:
                    for direction in ("input", "output"):
                        for rep in contract[direction].get("representations", []):
                            if "schema" in rep:
                                path = (
                                    "/flight-input.json"
                                    if direction == "input"
                                    else "/flight-output.json"
                                )
                                rep["schema"] = {
                                    "dialect": "https://json-schema.org/draft/2020-12/schema",
                                    "mediaType": "application/schema+json",
                                    "uri": origin + path,
                                    "integrity": pins[origin + path],
                                }
                catalog["contracts"].append(
                    {
                        "id": "urn:reference:external-echo:1",
                        "input": {
                            "presence": "required",
                            "representations": [representation],
                        },
                        "output": {
                            "presence": "required",
                            "representations": [representation],
                        },
                    }
                )
                catalog_body = json.dumps(
                    catalog, separators=(",", ":"), ensure_ascii=False
                ).encode()
                catalogs[hostname] = catalog_body
                pins[origin + "/catalog.json"] = pin(catalog_body)
                catalog_path, pins_path = (
                    directory / f"{side}-catalog.json",
                    directory / f"{side}-pins.json",
                )
                catalog_path.write_bytes(catalog_body)
                pins_path.write_text(json.dumps(pins))
                configurations[side] = {
                    "origin": origin,
                    "catalog": str(catalog_path),
                    "pins": str(pins_path),
                    "ca": str(CERT),
                }
            configuration = directory / "config.json"
            configuration.write_text(json.dumps(configurations))
            result = subprocess.run(
                [
                    args.python,
                    str(ROOT / "interoperability/run.py"),
                    "--python",
                    args.python,
                    "--node",
                    args.node,
                    "--python-wheel",
                    args.python_wheel,
                    "--node-artifact",
                    args.node_artifact,
                    "--isolated-cwd",
                    args.isolated_cwd,
                    "--report",
                    args.report,
                    "--external-config",
                    str(configuration),
                ],
                check=False,
                timeout=180,
            )
            if result.returncode:
                raise RuntimeError("External profile failed; inspect report")
            if any(
                path not in requests
                for path in (
                    "/catalog.json",
                    "/root.json",
                    "/types.json",
                    "/flight-input.json",
                    "/flight-output.json",
                )
            ):
                raise RuntimeError(
                    "Fixture did not serve the catalog and all schema resources"
                )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
