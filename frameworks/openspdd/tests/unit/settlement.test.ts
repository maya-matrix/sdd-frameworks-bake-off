import fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { greedySettle, suggestTransfers } from '../../src/domain/settlement.js';
import type { Balance, Transfer } from '../../src/domain/types.js';

const balances = (nets: bigint[]): Balance[] => nets.map((net, i) => ({ memberId: `m${i}`, net }));

function apply(input: Balance[], transfers: Transfer[]): Map<string, bigint> {
  const net = new Map(input.map((b) => [b.memberId, b.net]));
  for (const t of transfers) {
    net.set(t.fromMemberId, (net.get(t.fromMemberId) ?? 0n) + t.amount);
    net.set(t.toMemberId, (net.get(t.toMemberId) ?? 0n) - t.amount);
  }
  return net;
}

function expectSettles(input: Balance[], transfers: Transfer[]): void {
  for (const t of transfers) {
    expect(t.amount > 0n).toBe(true);
    expect(t.fromMemberId).not.toBe(t.toMemberId);
  }
  for (const value of apply(input, transfers).values()) {
    expect(value).toBe(0n);
  }
}

/** Exhaustive maximum number of disjoint zero-sum subsets covering all values. */
function maxZeroSumParts(values: bigint[]): number {
  if (values.length === 0) return 0;
  const [first, ...rest] = values as [bigint, ...bigint[]];
  let best = 0;
  for (let mask = 0; mask < 1 << rest.length; mask++) {
    let sum = first;
    const remaining: bigint[] = [];
    rest.forEach((v, i) => {
      if (mask & (1 << i)) sum += v;
      else remaining.push(v);
    });
    if (sum === 0n) best = Math.max(best, 1 + maxZeroSumParts(remaining));
  }
  return best;
}

const zeroSumNets = fc
  .array(
    fc.integer({ min: -50, max: 50 }).filter((x) => x !== 0),
    { minLength: 1, maxLength: 7 },
  )
  .map((xs) => {
    const nets = xs.map(BigInt);
    const total = nets.reduce((a, b) => a + b, 0n);
    if (total !== 0n) nets.push(-total);
    return nets;
  });

describe('suggestTransfers', () => {
  it('returns no transfers for empty or all-zero balances', () => {
    expect(suggestTransfers([])).toEqual({ transfers: [], optimal: true });
    expect(suggestTransfers(balances([0n, 0n]))).toEqual({ transfers: [], optimal: true });
  });

  it('settles a simple pair with one transfer from debtor to creditor', () => {
    expect(suggestTransfers(balances([5n, -5n]))).toEqual({
      transfers: [{ fromMemberId: 'm1', toMemberId: 'm0', amount: 5n }],
      optimal: true,
    });
  });

  it('beats plain greedy when zero-sum subgroups exist', () => {
    const input = balances([6n, 4n, 3n, -7n, -6n]);
    expect(greedySettle(input)).toHaveLength(4);
    const plan = suggestTransfers(input);
    expect(plan.transfers).toHaveLength(3);
    expect(plan.optimal).toBe(true);
    expectSettles(input, plan.transfers);
  });

  it('produces the proven minimum number of transfers', () => {
    fc.assert(
      fc.property(zeroSumNets, (nets) => {
        const input = balances(nets);
        const plan = suggestTransfers(input);
        expectSettles(input, plan.transfers);
        expect(plan.optimal).toBe(true);
        expect(plan.transfers).toHaveLength(nets.length - maxZeroSumParts(nets));
      }),
      { numRuns: 300 },
    );
  });

  it('falls back to greedy above 16 non-zero balances', () => {
    const nets = Array.from({ length: 16 }, (_, i) => BigInt(i + 1));
    nets.push(-nets.reduce((a, b) => a + b, 0n));
    const input = balances(nets);
    const plan = suggestTransfers(input);
    expect(plan.optimal).toBe(false);
    expect(plan.transfers.length).toBeLessThanOrEqual(16);
    expectSettles(input, plan.transfers);
  });

  it('solves 16 distinct non-zero balances in under a second', () => {
    const nets = Array.from({ length: 15 }, (_, i) => BigInt((i + 1) * 101));
    nets.push(-nets.reduce((a, b) => a + b, 0n));
    const input = balances(nets);
    const start = performance.now();
    const plan = suggestTransfers(input);
    expect(performance.now() - start).toBeLessThan(1000);
    expect(plan.optimal).toBe(true);
    expectSettles(input, plan.transfers);
  });

  it('is deterministic', () => {
    const input = balances([10n, -3n, -3n, 4n, -8n]);
    expect(suggestTransfers(input)).toEqual(suggestTransfers(input));
  });
});
