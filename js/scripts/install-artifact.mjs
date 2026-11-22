import { createHash } from 'node:crypto';
import { readFile, mkdir, mkdtemp, readdir, rm, writeFile, realpath } from 'node:fs/promises';
import { resolve, sep, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { npm } from './process.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const configuration = JSON.parse(
  await readFile(new URL('../artifact-input.json', import.meta.url), 'utf8'),
);
const input = process.env.SDK_ARTIFACT;
if (!input) throw new Error('Set SDK_ARTIFACT to an npm tarball path; see js/README.md');
const artifact = await readFile(resolve(input));
const hash = createHash('sha256').update(artifact).digest('hex');
if (hash !== configuration.sha256)
  throw new Error('SDK artifact SHA-256 mismatch; no installation attempted');
const lock = JSON.parse(await readFile(resolve(root, 'package-lock.json'), 'utf8'));
const lockEntry = lock.packages?.['node_modules/' + configuration.packageName];
const integrity = 'sha512-' + createHash('sha512').update(artifact).digest('base64');
if (lockEntry?.resolved !== 'file:artifacts/sdk.tgz' || lockEntry.integrity !== integrity)
  throw new Error('SDK artifact does not match lockfile integrity; no installation attempted');
await mkdir(resolve(root, 'artifacts'), { recursive: true });
const staged = resolve(root, 'artifacts/sdk.tgz');
await writeFile(staged, artifact);
await npm(['ci', '--ignore-scripts'], { cwd: root });
const installedRoot = resolve(root, 'node_modules', configuration.packageName);
const installed = JSON.parse(await readFile(resolve(installedRoot, 'package.json'), 'utf8'));
if (installed.version !== configuration.version) throw new Error('Installed SDK version mismatch');
// npm can reuse an older cached file: dependency with the same name/version.
// Verify the actual installed bytes, rather than treating the staged hash as proof.
const extracted = await mkdtemp(join(tmpdir(), 'a2a-sdk-artifact-'));
try {
  await promisify(execFile)('tar', ['-xzf', staged, '-C', extracted]);
  const expectedRoot = join(extracted, 'package');
  let count = 0;
  async function verify(relative = '') {
    for (const entry of await readdir(join(expectedRoot, relative), { withFileTypes: true })) {
      const path = join(relative, entry.name);
      if (entry.isDirectory()) await verify(path);
      else if (entry.isFile()) {
        if (
          !(await readFile(join(expectedRoot, path))).equals(
            await readFile(join(installedRoot, path)),
          )
        )
          throw new Error('Installed SDK differs from reviewed artifact: ' + path);
        count++;
      } else throw new Error('Unsupported SDK artifact entry: ' + path);
    }
  }
  await verify();
  if (!count) throw new Error('SDK artifact contains no package files');
} finally {
  await rm(extracted, { recursive: true, force: true });
}
const corePath = await realpath(
  fileURLToPath(import.meta.resolve(configuration.packageName + '/core')),
);
if (!corePath.startsWith((await realpath(installedRoot)) + sep))
  throw new Error('SDK resolved outside installed artifact');
await mkdir(resolve(root, 'reports'), { recursive: true });
await writeFile(
  resolve(root, 'reports/artifact.json'),
  JSON.stringify(
    {
      ...configuration,
      node: process.version,
      installation: 'npm tarball; no source imports',
      result: 'PASS',
    },
    null,
    2,
  ) + '\n',
);
console.log(JSON.stringify({ artifact: configuration.version, sha256: hash, result: 'PASS' }));
