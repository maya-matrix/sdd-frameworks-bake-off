import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildApp } from '../../src/app.js';
import { addMember, createGroup, recordExpense, toCents } from './helpers.js';

let app: FastifyInstance;
let groupId: string;
let a: string;
let b: string;
let c: string;

beforeEach(async () => {
  app = buildApp();
  groupId = await createGroup(app);
  a = await addMember(app, groupId, 'A');
  b = await addMember(app, groupId, 'B');
  c = await addMember(app, groupId, 'C');
});

afterEach(async () => {
  await app.close();
});

const balances = async () =>
  (await app.inject({ method: 'GET', url: `/groups/${groupId}/balances` })).json().balances as Array<{
    memberId: string;
    name: string;
    net: string;
  }>;

const settleUp = async () => (await app.inject({ method: 'GET', url: `/groups/${groupId}/settle-up` })).json();

describe('balances and settle-up', () => {
  it('computes balances and settling transfers end-to-end', async () => {
    await recordExpense(app, groupId, { payerId: a, amount: '90.00', description: 'Hotel', participantIds: [a, b, c] });
    await recordExpense(app, groupId, { payerId: b, amount: '30.00', description: 'Taxi', participantIds: [b, c] });

    expect(await balances()).toEqual([
      { memberId: a, name: 'A', net: '60.00' },
      { memberId: b, name: 'B', net: '-15.00' },
      { memberId: c, name: 'C', net: '-45.00' },
    ]);
    expect(await settleUp()).toEqual({
      transfers: [
        { from: { id: c, name: 'C' }, to: { id: a, name: 'A' }, amount: '45.00' },
        { from: { id: b, name: 'B' }, to: { id: a, name: 'A' }, amount: '15.00' },
      ],
      optimal: true,
    });
  });

  it('keeps cents exact where floating point would drift', async () => {
    for (const amount of ['0.10', '0.20', '0.10', '0.20', '0.10', '0.20']) {
      await recordExpense(app, groupId, { payerId: a, amount, description: 'Gum', participantIds: [b] });
    }
    const result = await balances();
    expect(result.map((x) => x.net)).toEqual(['0.90', '-0.90', '0.00']);
  });

  it('keeps balances summing to zero with indivisible splits, and settle-up clears them', async () => {
    await recordExpense(app, groupId, { payerId: a, amount: '10.00', description: 'x', participantIds: [a, b, c] });
    await recordExpense(app, groupId, { payerId: b, amount: '0.01', description: 'y', participantIds: [c, a] });
    await recordExpense(app, groupId, { payerId: c, amount: '7.77', description: 'z', participantIds: [b, a, c] });

    const result = await balances();
    expect(result.reduce((sum, x) => sum + toCents(x.net), 0n)).toBe(0n);

    const net = new Map(result.map((x) => [x.memberId, toCents(x.net)]));
    const plan = await settleUp();
    for (const t of plan.transfers as Array<{ from: { id: string }; to: { id: string }; amount: string }>) {
      net.set(t.from.id, (net.get(t.from.id) ?? 0n) + toCents(t.amount));
      net.set(t.to.id, (net.get(t.to.id) ?? 0n) - toCents(t.amount));
    }
    expect([...net.values()].every((v) => v === 0n)).toBe(true);
  });

  it('returns zero balances and no transfers when there are no expenses', async () => {
    expect((await balances()).map((x) => x.net)).toEqual(['0.00', '0.00', '0.00']);
    expect(await settleUp()).toEqual({ transfers: [], optimal: true });
  });

  it('returns 404 for an unknown group on both endpoints', async () => {
    for (const url of ['/groups/nope/balances', '/groups/nope/settle-up']) {
      const res = await app.inject({ method: 'GET', url });
      expect(res.statusCode).toBe(404);
      expect(res.json().error.code).toBe('GROUP_NOT_FOUND');
    }
  });
});
