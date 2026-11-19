import { manifest, runScenario } from '../js/src/client/run.mjs';

const [url, id] = process.argv.slice(2);
const scenario = manifest.scenarios.find((item) => item.id === id);
if (!url || !scenario) throw new Error('Expected URL and known scenario ID');
console.log(JSON.stringify(await runScenario(url, scenario)));
