import assert from 'node:assert/strict';
import { CancelTaskRequest, TaskState } from '@a2a-js/sdk';
import { discoverContractClient } from 'a2a-schema-contract/client';
const url = process.argv[2];
const client = await discoverContractClient(url);
try {
  const before = await (await fetch(url + '/evidence')).json();
  const iterator = client.stream(
    {
      contractId: 'urn:reference:invoice:1',
      input: { representationId: 'json', value: { quantity: 3, unitPrice: 7, label: null } },
      metadata: { fault: 'wait' },
    },
    { signal: AbortSignal.timeout(10000) },
  );
  try {
    const first = await iterator.next();
    assert.equal(first.value.kind, 'companion');
    const taskId = first.value.event.payload.value.id;
    assert.ok(taskId);
    const canceled = await client.client.cancelTask(CancelTaskRequest.fromJSON({ id: taskId }));
    assert.equal(canceled.status.state, TaskState.TASK_STATE_CANCELED);
    const rest = [];
    for await (const event of iterator) rest.push(event);
    assert.equal(rest.at(-1).result.response.status.state, TaskState.TASK_STATE_CANCELED);
    assert.deepEqual(rest.at(-1).result.response.artifacts, []);
    const after = await (await fetch(url + '/evidence')).json();
    assert.equal(after.executions, before.executions + 1);
    console.log(JSON.stringify({ id: 'explicit-cancel', outcome: 'PASS', executions: 1 }));
  } finally {
    await iterator.return();
  }
} finally {
  await client.close();
}
