import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { discoverContractClient } from 'a2a-schema-contract/client';
import { createContractResolver } from 'a2a-schema-contract/resolver';

const [url, origin, caPath, pinsPath] = process.argv.slice(2);
const pins = JSON.parse(await readFile(pinsPath, 'utf8'));
const options = {
  allowedOrigins: [origin],
  ca: await readFile(caPath),
  lookup: () => Promise.resolve([{ address: '127.0.0.1', family: 4 }]),
  allowAddress: (address, hostname) =>
    address === '127.0.0.1' && ['127.0.0.1', 'catalog.test'].includes(hostname),
};
const resolver = createContractResolver({ ...options, resourceIntegrity: pins });
const client = await discoverContractClient(url, { resolver });
try {
  const id = 'urn:reference:external-echo:1';
  const schema = client.catalog.schema(id, 'input', 'json');
  assert.equal(schema.documents.length, 2);
  const result = await client.invoke({
    contractId: id,
    input: { representationId: 'json', value: { text: 'external fixture' } },
    acceptedOutputRepresentationIds: ['json'],
  });
  assert.deepEqual(result.payload.value, { text: 'external fixture' });
  resolver.clearCache();
  assert.equal(client.catalog.schema(id, 'input', 'json').documents.length, 2);
  const before = (await (await fetch(url + '/evidence')).json()).executions;
  const badPins = {
    ...pins,
    [origin + '/types.json']: { algorithm: 'sha-256', value: Buffer.alloc(32).toString('base64') },
  };
  const badResolver = createContractResolver({ ...options, resourceIntegrity: badPins });
  await assert.rejects(discoverContractClient(url, { resolver: badResolver }), {
    code: 'INTEGRITY_MISMATCH',
  });
  assert.equal((await (await fetch(url + '/evidence')).json()).executions, before);
  console.log(JSON.stringify({ id: 'external-transitive', outcome: 'PASS' }));
} finally {
  await client.close();
}
