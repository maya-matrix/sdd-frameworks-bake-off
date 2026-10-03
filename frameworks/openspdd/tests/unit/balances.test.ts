import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { computeBalances } from '../../src/domain/balances.js';
import { splitEqually } from '../../src/domain/money.js';
import type { Expense, Member } from '../../src/domain/types.js';

const member = (id: string, seq: number): Member => ({ id, groupId: 'g', name: id, seq });

function expense(payerId: string, amount: bigint, participantIds: string[]): Expense {
  const amounts = splitEqually(amount, participantIds.length);
  return {
    id: `${payerId}-${amount}`,
    groupId: 'g',
    payerId,
    amount,
    description: 'test',
    shares: participantIds.map((memberId, i) => ({ memberId, amount: amounts[i] as bigint })),
    createdAt: '2026-01-01T00:00:00.000Z',
  };
}

describe('computeBalances', () => {
  const members = [member('a', 0), member('b', 1), member('c', 2)];

  it('credits a non-participating payer with the full amount', () => {
    const balances = computeBalances(members, [expense('a', 1000n, ['b', 'c'])]);
    expect(balances).toEqual([
      { memberId: 'a', net: 1000n },
      { memberId: 'b', net: -500n },
      { memberId: 'c', net: -500n },
    ]);
  });

  it('treats a payer-only expense as net zero', () => {
    const balances = computeBalances(members, [expense('b', 777n, ['b'])]);
    expect(balances.map((b) => b.net)).toEqual([0n, 0n, 0n]);
  });

  it('includes inactive members with zero and orders by seq', () => {
    const shuffled = [member('c', 2), member('a', 0), member('b', 1)];
    const balances = computeBalances(shuffled, [expense('a', 300n, ['a', 'b'])]);
    expect(balances).toEqual([
      { memberId: 'a', net: 150n },
      { memberId: 'b', net: -150n },
      { memberId: 'c', net: 0n },
    ]);
  });

  it('always sums to exactly zero', () => {
    const ids = ['a', 'b', 'c', 'd', 'e'];
    const all = ids.map((id, seq) => member(id, seq));
    const arbExpense = fc
      .record({
        payer: fc.constantFrom(...ids),
        amount: fc.bigInt({ min: 1n, max: 999_999_999_999n }),
        participants: fc.subarray(ids, { minLength: 1 }),
      })
      .map((e) => expense(e.payer, e.amount, e.participants));
    fc.assert(
      fc.property(fc.array(arbExpense, { maxLength: 30 }), (expenses) => {
        const total = computeBalances(all, expenses).reduce((s, b) => s + b.net, 0n);
        expect(total).toBe(0n);
      }),
    );
  });
});
