import { after, before, describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';

let server;
let baseUrl;

before(async () => {
  server = createApp();
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  baseUrl = `http://127.0.0.1:${server.address().port}`;
});

after(() => new Promise((resolve) => server.close(resolve)));

async function call(method, path, { as, body, rawBody } = {}) {
  const headers = { 'content-type': 'application/json' };
  if (as) headers['x-user-id'] = as;
  const res = await fetch(baseUrl + path, {
    method,
    headers,
    body: rawBody ?? (body === undefined ? undefined : JSON.stringify(body)),
  });
  return { status: res.status, body: await res.json() };
}

async function createUser(name) {
  const res = await call('POST', '/users', { body: { name } });
  assert.equal(res.status, 201);
  return res.body.id;
}

/** Create a group owned by the first user with all given users as members. */
async function createGroup(name, owner, ...others) {
  const res = await call('POST', '/groups', { as: owner, body: { name } });
  assert.equal(res.status, 201);
  for (const userId of others) {
    const added = await call('POST', `/groups/${res.body.id}/members`, { as: owner, body: { userId } });
    assert.equal(added.status, 201);
  }
  return res.body.id;
}

async function addExpense(groupId, as, expense) {
  const res = await call('POST', `/groups/${groupId}/expenses`, { as, body: expense });
  assert.equal(res.status, 201, JSON.stringify(res.body));
  return res.body;
}

const balanceMap = (body) => Object.fromEntries(body.balances.map((b) => [b.userId, b.balance]));

describe('users and groups', () => {
  test('creating a group makes the creator its first member', async () => {
    const alice = await createUser('Alice');
    const res = await call('POST', '/groups', { as: alice, body: { name: 'Trip' } });
    assert.equal(res.status, 201);
    assert.equal(res.body.name, 'Trip');
    assert.deepEqual(res.body.members, [{ id: alice, name: 'Alice' }]);
  });

  test('members can add other users; duplicates are rejected', async () => {
    const alice = await createUser('Alice');
    const bob = await createUser('Bob');
    const carol = await createUser('Carol');
    const groupId = await createGroup('Flat', alice, bob);

    // Any member (not just the creator) can add members.
    const res = await call('POST', `/groups/${groupId}/members`, { as: bob, body: { userId: carol } });
    assert.equal(res.status, 201);
    assert.deepEqual(res.body.members.map((m) => m.name), ['Alice', 'Bob', 'Carol']);

    const dup = await call('POST', `/groups/${groupId}/members`, { as: alice, body: { userId: bob } });
    assert.equal(dup.status, 409);

    const unknown = await call('POST', `/groups/${groupId}/members`, { as: alice, body: { userId: 'nope' } });
    assert.equal(unknown.status, 404);
  });

  test('authentication and membership are enforced', async () => {
    const alice = await createUser('Alice');
    const mallory = await createUser('Mallory');
    const groupId = await createGroup('Private', alice);

    assert.equal((await call('POST', '/groups', { body: { name: 'x' } })).status, 401);
    assert.equal((await call('POST', '/groups', { as: 'ghost', body: { name: 'x' } })).status, 401);
    assert.equal((await call('GET', `/groups/${groupId}`, { as: mallory })).status, 403);
    assert.equal((await call('GET', `/groups/${groupId}/balances`, { as: mallory })).status, 403);
    assert.equal((await call('POST', `/groups/${groupId}/members`, { as: mallory, body: { userId: mallory } })).status, 403);
    assert.equal((await call('GET', '/groups/does-not-exist', { as: alice })).status, 404);
  });

  test('validates names and request bodies', async () => {
    assert.equal((await call('POST', '/users', { body: { name: '  ' } })).status, 400);
    assert.equal((await call('POST', '/users', { body: {} })).status, 400);
    assert.equal((await call('POST', '/users', { rawBody: '{not json' })).status, 400);
    assert.equal((await call('POST', '/users', { rawBody: '[1,2]' })).status, 400);
  });

  test('unknown routes return 404 and wrong methods return 405', async () => {
    assert.equal((await call('GET', '/nope')).status, 404);
    assert.equal((await call('DELETE', '/users')).status, 405);
  });
});

describe('expenses', () => {
  test('records an expense split equally with exact cents', async () => {
    const [a, b, c] = [await createUser('A'), await createUser('B'), await createUser('C')];
    const groupId = await createGroup('G', a, b, c);

    const expense = await addExpense(groupId, b, {
      paidBy: a,
      amount: '10.00',
      description: 'Pizza',
      splitBetween: [a, b, c],
    });
    assert.equal(expense.amount, '10.00');
    assert.equal(expense.paidBy, a);
    assert.equal(expense.createdBy, b);
    assert.deepEqual(expense.splitBetween, [
      { userId: a, amount: '3.34' },
      { userId: b, amount: '3.33' },
      { userId: c, amount: '3.33' },
    ]);

    const list = await call('GET', `/groups/${groupId}/expenses`, { as: c });
    assert.equal(list.status, 200);
    assert.deepEqual(list.body, [expense]);
  });

  test('rejects invalid expenses', async () => {
    const [a, b] = [await createUser('A'), await createUser('B')];
    const outsider = await createUser('Outsider');
    const groupId = await createGroup('G', a, b);
    const valid = { paidBy: a, amount: '5.00', description: 'Coffee', splitBetween: [a, b] };

    const cases = [
      { amount: 5 }, // numbers are rejected to keep floats out of money handling
      { amount: '5.001' },
      { amount: '0' },
      { amount: '-5' },
      { amount: undefined },
      { description: '' },
      { paidBy: outsider },
      { paidBy: undefined },
      { splitBetween: [] },
      { splitBetween: 'a' },
      { splitBetween: [a, a] },
      { splitBetween: [a, outsider] },
      { splitBetween: [a, 7] },
    ];
    for (const override of cases) {
      const res = await call('POST', `/groups/${groupId}/expenses`, { as: a, body: { ...valid, ...override } });
      assert.equal(res.status, 400, `expected 400 for ${JSON.stringify(override)}`);
      assert.equal(res.body.error.code, 'validation_error');
    }

    const nonMember = await call('POST', `/groups/${groupId}/expenses`, { as: outsider, body: valid });
    assert.equal(nonMember.status, 403);

    const list = await call('GET', `/groups/${groupId}/expenses`, { as: a });
    assert.deepEqual(list.body, []);
  });
});

describe('balances and settle-up', () => {
  test('net balances reflect payments and shares, and always sum to zero', async () => {
    const [a, b, c] = [await createUser('A'), await createUser('B'), await createUser('C')];
    const groupId = await createGroup('G', a, b, c);

    await addExpense(groupId, a, { paidBy: a, amount: '10.00', description: 'Pizza', splitBetween: [a, b, c] });
    await addExpense(groupId, b, { paidBy: b, amount: '0.10', description: 'Gum', splitBetween: [b, c] });
    await addExpense(groupId, c, { paidBy: c, amount: '0.20', description: 'Mint', splitBetween: [a, b] });

    const res = await call('GET', `/groups/${groupId}/balances`, { as: a });
    assert.equal(res.status, 200);
    // A: +10.00 - 3.34 - 0.10 = 6.56
    // B: -3.33 + 0.10 - 0.05 - 0.10 = -3.38
    // C: -3.33 - 0.05 + 0.20 = -3.18
    assert.deepEqual(balanceMap(res.body), { [a]: '6.56', [b]: '-3.38', [c]: '-3.18' });
    assert.deepEqual(res.body.balances.map((x) => x.name), ['A', 'B', 'C']);

    const total = res.body.balances.reduce((sum, x) => sum + BigInt(x.balance.replace('.', '')), 0n);
    assert.equal(total, 0n);
  });

  test('members with no expenses show a zero balance', async () => {
    const [a, b] = [await createUser('A'), await createUser('B')];
    const groupId = await createGroup('G', a, b);
    const res = await call('GET', `/groups/${groupId}/balances`, { as: b });
    assert.deepEqual(balanceMap(res.body), { [a]: '0.00', [b]: '0.00' });

    const settle = await call('GET', `/groups/${groupId}/settle-up`, { as: b });
    assert.deepEqual(settle.body, { groupId, optimal: true, transfers: [] });
  });

  test('settle-up suggests the minimum transfers that clear all balances', async () => {
    const names = ['A', 'B', 'C', 'D', 'E', 'F'];
    const ids = [];
    for (const n of names) ids.push(await createUser(n));
    const [a, b, c, d, e, f] = ids;
    const groupId = await createGroup('Holiday', a, b, c, d, e, f);

    // Two independent sub-groups: {A,B,C} and {D,E,F}. Each needs 2 transfers.
    await addExpense(groupId, a, { paidBy: a, amount: '30.00', description: 'Dinner', splitBetween: [a, b, c] });
    await addExpense(groupId, d, { paidBy: d, amount: '90.00', description: 'Taxi', splitBetween: [d, e, f] });
    // A chain that cancels out: B pays for C, C pays for B, same amount.
    await addExpense(groupId, b, { paidBy: b, amount: '5.00', description: 'Snack', splitBetween: [c] });
    await addExpense(groupId, c, { paidBy: c, amount: '5.00', description: 'Snack', splitBetween: [b] });

    const balances = balanceMap((await call('GET', `/groups/${groupId}/balances`, { as: a })).body);
    assert.deepEqual(balances, {
      [a]: '20.00', [b]: '-10.00', [c]: '-10.00',
      [d]: '60.00', [e]: '-30.00', [f]: '-30.00',
    });

    const res = await call('GET', `/groups/${groupId}/settle-up`, { as: f });
    assert.equal(res.status, 200);
    assert.equal(res.body.optimal, true);
    assert.equal(res.body.transfers.length, 4);

    // Applying the suggested transfers clears every balance exactly.
    const net = Object.fromEntries(Object.entries(balances).map(([id, v]) => [id, BigInt(v.replace('.', ''))]));
    for (const t of res.body.transfers) {
      assert.match(t.amount, /^\d+\.\d{2}$/);
      const cents = BigInt(t.amount.replace('.', ''));
      net[t.from] += cents;
      net[t.to] -= cents;
      assert.equal(t.fromName, names[ids.indexOf(t.from)]);
      assert.equal(t.toName, names[ids.indexOf(t.to)]);
    }
    assert.ok(Object.values(net).every((v) => v === 0n));
  });

  test('many awkward splits stay exact to the cent', async () => {
    const ids = [];
    for (let i = 0; i < 7; i++) ids.push(await createUser(`U${i}`));
    const groupId = await createGroup('Big', ...ids);

    // 0.01 split seven ways, repeatedly, alongside amounts that are inexact in binary floating point.
    for (let i = 0; i < 50; i++) {
      await addExpense(groupId, ids[i % 7], {
        paidBy: ids[i % 7],
        amount: ['0.01', '0.10', '0.30', '33.33', '100.00'][i % 5],
        description: `Item ${i}`,
        splitBetween: ids.slice(0, 2 + (i % 6)),
      });
    }

    const balances = (await call('GET', `/groups/${groupId}/balances`, { as: ids[0] })).body.balances;
    const total = balances.reduce((sum, x) => sum + BigInt(x.balance.replace('.', '')), 0n);
    assert.equal(total, 0n);

    const settle = (await call('GET', `/groups/${groupId}/settle-up`, { as: ids[0] })).body;
    const net = Object.fromEntries(balances.map((x) => [x.userId, BigInt(x.balance.replace('.', ''))]));
    for (const t of settle.transfers) {
      const cents = BigInt(t.amount.replace('.', ''));
      net[t.from] += cents;
      net[t.to] -= cents;
    }
    assert.ok(Object.values(net).every((v) => v === 0n));
    assert.ok(settle.transfers.length <= balances.filter((x) => x.balance !== '0.00').length - 1);
  });
});
