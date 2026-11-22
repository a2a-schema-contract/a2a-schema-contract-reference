import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawn } from 'node:child_process';
import { cp, mkdir, mkdtemp, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { getSchemaResource } from 'a2a-schema-contract/core';

test('installed public imports and packaged resource resolve inside this consumer', async () => {
  const root = await realpath(new URL('../node_modules/a2a-schema-contract/', import.meta.url));
  for (const path of ['core', 'client', 'server', 'adapters/a2a-js']) {
    const installed = await realpath(
      fileURLToPath(import.meta.resolve('a2a-schema-contract/' + path)),
    );
    assert.ok(installed.startsWith(root + sep));
  }
  const resource = getSchemaResource('catalog');
  assert.ok((await realpath(resource)).startsWith(root + sep));
  assert.equal(JSON.parse(await readFile(resource, 'utf8')).type, 'object');
});
test(
  'tampered artifact fails before installation and preserves lock and installed package',
  { timeout: 5000 },
  async () => {
    const dir = await mkdtemp(join(tmpdir(), 'reference-bad-artifact-'));
    const lockUrl = new URL('../package-lock.json', import.meta.url);
    const sdkUrl = new URL('../node_modules/a2a-schema-contract/package.json', import.meta.url);
    const beforeLock = await readFile(lockUrl, 'utf8');
    const beforeSDK = await readFile(sdkUrl, 'utf8');
    try {
      const input = join(dir, 'bad.tgz');
      await writeFile(input, 'tampered');
      const child = spawn(
        process.execPath,
        [fileURLToPath(new URL('../scripts/install-artifact.mjs', import.meta.url))],
        { env: { ...process.env, SDK_ARTIFACT: input }, stdio: ['ignore', 'ignore', 'pipe'] },
      );
      let diagnostic = '';
      child.stderr.on('data', (chunk) => {
        diagnostic += chunk.toString();
      });
      const code = await new Promise((resolve, reject) => {
        child.once('error', reject);
        child.once('exit', resolve);
      });
      assert.equal(code, 1);
      assert.match(diagnostic, /SHA-256 mismatch; no installation attempted/);
      assert.equal(await readFile(lockUrl, 'utf8'), beforeLock);
      assert.equal(await readFile(sdkUrl, 'utf8'), beforeSDK);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  },
);

test(
  'a stale lockfile rejects the correct artifact before any installation',
  { timeout: 5000 },
  async () => {
    const dir = await mkdtemp(join(tmpdir(), 'reference-stale-lock-'));
    try {
      await mkdir(join(dir, 'scripts'));
      for (const filename of ['install-artifact.mjs', 'process.mjs'])
        await cp(
          new URL('../scripts/' + filename, import.meta.url),
          join(dir, 'scripts', filename),
        );
      await cp(
        new URL('../artifact-input.json', import.meta.url),
        join(dir, 'artifact-input.json'),
      );
      const lock = JSON.parse(
        await readFile(new URL('../package-lock.json', import.meta.url), 'utf8'),
      );
      lock.packages['node_modules/a2a-schema-contract'].integrity = 'sha512-stale';
      await writeFile(join(dir, 'package-lock.json'), JSON.stringify(lock));
      const child = spawn(process.execPath, [join(dir, 'scripts/install-artifact.mjs')], {
        env: {
          ...process.env,
          SDK_ARTIFACT: fileURLToPath(new URL('../artifacts/sdk.tgz', import.meta.url)),
        },
        stdio: ['ignore', 'ignore', 'pipe'],
      });
      let diagnostic = '';
      child.stderr.on('data', (chunk) => {
        diagnostic += chunk.toString();
      });
      const code = await new Promise((resolve, reject) => {
        child.once('error', reject);
        child.once('exit', resolve);
      });
      assert.equal(code, 1);
      assert.match(diagnostic, /lockfile integrity; no installation attempted/);
      await assert.rejects(readFile(join(dir, 'artifacts/sdk.tgz')), { code: 'ENOENT' });
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  },
);
