import { readFile } from "node:fs/promises";
import { runScenario } from "../js/src/client/run.mjs";

const [url, id, manifestPath] = process.argv.slice(2);
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const scenario = manifest.scenarios.find((item) => item.id === id);
if (!url || !scenario) throw new Error("Expected URL and known scenario ID");
console.log(JSON.stringify(await runScenario(url, scenario)));
