import assert from 'node:assert/strict';
import { discoverContractClient } from 'a2a-schema-contract/client';

const url = process.argv[2];
const id = 'urn:reference:flight-search:1';
const client = await discoverContractClient(url);
try {
  const description = await client.describe();
  assert.deepEqual(
    description.skills.map((item) => item.contracts.length),
    [4, 2, 0],
  );
  assert.equal(description.unassociated.length, 1);
  assert.deepEqual(description.staleAssociations, [
    { contractId: 'urn:reference:flight-search:5', skillId: 'missing-skill' },
  ]);
  assert.equal(description.skills[0].contracts[3].input[0].diagnostic, 'UNSUPPORTED_MEDIA_TYPE');
  const schema = client.catalog.schema(id, 'input', 'json');
  assert.deepEqual(schema.documents[0].value.required, ['origin', 'destination']);
  const before = (await (await fetch(url + '/evidence')).json()).executions;
  await assert.rejects(client.invokeContract({ contractId: id, input: { origin: 'BLR' } }), {
    code: 'INSTANCE_INVALID',
  });
  assert.equal((await (await fetch(url + '/evidence')).json()).executions, before);
  const result = await client.invokeContract({
    contractId: id,
    input: { origin: 'BLR', destination: 'DEL' },
  });
  assert.deepEqual(result.payload.value, {
    flights: [{ flightNumber: 'REF101', origin: 'BLR', destination: 'DEL' }],
  });
  console.log(JSON.stringify({ id: 'skill-discovery', outcome: 'PASS' }));
} finally {
  await client.close();
}
