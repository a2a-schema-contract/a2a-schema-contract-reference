import assert from 'node:assert/strict';
import { discoverContractClient } from 'a2a-schema-contract/client';

const url = process.argv[2];
const before = (await (await fetch(url + '/evidence')).json()).executions;
let mutated = false;
const client = await discoverContractClient(url, {
  fetchImpl: async (input, init) => {
    const response = await fetch(input, init);
    if (init?.method !== 'POST') return response;
    const body = await response.json();
    const part = body.result.task.artifacts[0].parts[0];
    part.data = { total: -1, label: null };
    mutated = true;
    return Response.json(body);
  },
});
try {
  await assert.rejects(
    client.invoke({
      contractId: 'urn:reference:invoice:1',
      input: { representationId: 'json', value: { quantity: 3, unitPrice: 7, label: null } },
      acceptedOutputRepresentationIds: ['rich'],
    }),
    { code: 'INSTANCE_INVALID' },
  );
  assert.equal(mutated, true);
  assert.equal((await (await fetch(url + '/evidence')).json()).executions, before + 1);
  console.log(JSON.stringify({ id: 'dishonest-output', outcome: 'PASS', executions: 1 }));
} finally {
  await client.close();
}
