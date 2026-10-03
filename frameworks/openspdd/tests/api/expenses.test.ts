import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildApp } from '../../src/app.js';
import { addMember, createGroup, recordExpense } from './helpers.js';

let app: FastifyInstance;
let groupId: string;
let alice: string;
let bob: string;
let carol: string;

beforeEach(async () => {
  app = buildApp();
  groupId = await createGroup(app);
  alice = await addMember(app, groupId, 'Alice');
  bob = await addMember(app, groupId, 'Bob');
  carol = await addMember(app, groupId, 'Carol');
});

afterEach(async () => {
  await app.close();
});

const valid = () => ({
  payerId: alice,
  amount: '10.00',
  description: 'Dinner',
  participantIds: [alice, bob, carol],
});

describe('recording expenses', () => {
  it('splits equally with leftover cents to the first-listed participants', async () => {
    const res = await recordExpense(app, groupId, valid());
    expect(res.statusCode).toBe(201);
    const body = res.json();
    expect(body).toMatchObject({ payerId: alice, amount: '10.00', description: 'Dinner' });
    expect(body.shares).toEqual([
      { memberId: alice, amount: '3.34' },
      { memberId: bob, amount: '3.33' },
      { memberId: carol, amount: '3.33' },
    ]);
  });

  it('allows the payer to not participate and allows zero shares', async () => {
    const res = await recordExpense(app, groupId, {
      ...valid(),
      amount: '0.02',
      participantIds: [bob, carol, alice],
    });
    expect(res.statusCode).toBe(201);
    expect(res.json().shares.map((s: { amount: string }) => s.amount)).toEqual(['0.01', '0.01', '0.00']);

    const payerOut = await recordExpense(app, groupId, { ...valid(), participantIds: [bob] });
    expect(payerOut.statusCode).toBe(201);
  });

  it('rejects a JSON number amount with 400 (no coercion)', async () => {
    const res = await recordExpense(app, groupId, { ...valid(), amount: 10 });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe('VALIDATION_ERROR');
  });

  it.each(['1.005', '-1.00', '1e3', 'abc'])('rejects malformed amount %j with 400', async (amount) => {
    const res = await recordExpense(app, groupId, { ...valid(), amount });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe('VALIDATION_ERROR');
  });

  it('rejects a zero amount with 422 INVALID_AMOUNT', async () => {
    const res = await recordExpense(app, groupId, { ...valid(), amount: '0.00' });
    expect(res.statusCode).toBe(422);
    expect(res.json().error.code).toBe('INVALID_AMOUNT');
  });

  it('rejects an unknown payer with 422 UNKNOWN_MEMBER', async () => {
    const res = await recordExpense(app, groupId, { ...valid(), payerId: 'ghost' });
    expect(res.statusCode).toBe(422);
    expect(res.json().error).toMatchObject({ code: 'UNKNOWN_MEMBER', details: { memberId: 'ghost' } });
  });

  it('rejects a participant from another group with 422 UNKNOWN_MEMBER', async () => {
    const other = await createGroup(app, 'Other');
    const outsider = await addMember(app, other, 'Dave');
    const res = await recordExpense(app, groupId, { ...valid(), participantIds: [alice, outsider] });
    expect(res.statusCode).toBe(422);
    expect(res.json().error).toMatchObject({ code: 'UNKNOWN_MEMBER', details: { memberId: outsider } });
  });

  it('rejects a duplicate participant with 422 DUPLICATE_PARTICIPANT', async () => {
    const res = await recordExpense(app, groupId, { ...valid(), participantIds: [alice, bob, alice] });
    expect(res.statusCode).toBe(422);
    expect(res.json().error.code).toBe('DUPLICATE_PARTICIPANT');
  });

  it.each([
    ['empty participants', { participantIds: [] }],
    ['blank description', { description: '  ' }],
    ['extra property', { currency: 'EUR' }],
  ])('rejects %s with 400', async (_label, override) => {
    const res = await recordExpense(app, groupId, { ...valid(), ...override });
    expect(res.statusCode).toBe(400);
  });

  it('returns 404 for an unknown group', async () => {
    const res = await recordExpense(app, 'nope', valid());
    expect(res.statusCode).toBe(404);
    expect(res.json().error.code).toBe('GROUP_NOT_FOUND');
  });
});

describe('listing expenses', () => {
  it('lists expenses in insertion order', async () => {
    await recordExpense(app, groupId, { ...valid(), description: 'First' });
    await recordExpense(app, groupId, { ...valid(), description: 'Second', amount: '5.50' });
    const res = await app.inject({ method: 'GET', url: `/groups/${groupId}/expenses` });
    expect(res.statusCode).toBe(200);
    const expenses = res.json().expenses;
    expect(expenses.map((e: { description: string }) => e.description)).toEqual(['First', 'Second']);
    expect(expenses[1].amount).toBe('5.50');
  });

  it('returns 404 for an unknown group', async () => {
    const res = await app.inject({ method: 'GET', url: '/groups/nope/expenses' });
    expect(res.statusCode).toBe(404);
  });
});
