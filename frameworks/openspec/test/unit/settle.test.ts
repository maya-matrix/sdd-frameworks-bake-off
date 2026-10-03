import { describe, expect, it } from "vitest";
import fc from "fast-check";
import type { Balance } from "../../src/domain/balances.js";
import { settleGreedily, settleUp, type Transfer } from "../../src/domain/settle.js";

function balances(values: Record<string, bigint>): Balance[] {
  return Object.entries(values).map(([memberId, balance]) => ({ memberId, balance }));
}

function apply(input: Balance[], transfers: Transfer[]): Map<string, bigint> {
  const result = new Map(input.map((b) => [b.memberId, b.balance]));
  for (const t of transfers) {
    result.set(t.from, result.get(t.from)! + t.amount);
    result.set(t.to, result.get(t.to)! - t.amount);
  }
  return result;
}

function expectValidPlan(input: Balance[], transfers: Transfer[]) {
  for (const value of apply(input, transfers).values()) {
    expect(value).toBe(0n);
  }
  const senders = new Set(transfers.map((t) => t.from));
  for (const t of transfers) {
    expect(t.amount > 0n).toBe(true);
    expect(t.from).not.toBe(t.to);
    expect(senders.has(t.to)).toBe(false);
  }
}

/** Independent brute force: largest number of disjoint zero-sum groups. */
function bruteMaxGroups(values: bigint[]): number {
  if (values.length === 0) return 0;
  const [first, ...rest] = values;
  let best = 0;
  const n = rest.length;
  for (let mask = 0; mask < 1 << n; mask++) {
    let sum = first!;
    const remaining: bigint[] = [];
    for (let i = 0; i < n; i++) {
      if (mask & (1 << i)) sum += rest[i]!;
      else remaining.push(rest[i]!);
    }
    if (sum === 0n) best = Math.max(best, 1 + bruteMaxGroups(remaining));
  }
  return best;
}

describe("settleGreedily", () => {
  it("settles a zero-sum group of size s in s − 1 transfers, debtors only sending", () => {
    const group = [
      { memberId: "a", rank: 0, balance: 900n },
      { memberId: "b", rank: 1, balance: 100n },
      { memberId: "c", rank: 2, balance: -300n },
      { memberId: "d", rank: 3, balance: -700n },
    ];
    const transfers = settleGreedily(group);
    expect(transfers.length).toBeLessThanOrEqual(group.length - 1);
    expectValidPlan(group, transfers);
    for (const t of transfers) {
      expect(["c", "d"]).toContain(t.from);
      expect(["a", "b"]).toContain(t.to);
    }
  });
});

describe("settleUp", () => {
  it("settles a simple debt", () => {
    const input = balances({ alice: 2000n, bob: -1000n, carol: -1000n });
    expect(settleUp(input)).toEqual({
      transfers: [
        { from: "bob", to: "alice", amount: 1000n },
        { from: "carol", to: "alice", amount: 1000n },
      ],
      optimal: true,
    });
  });

  it("returns no transfers when everything is settled", () => {
    expect(settleUp(balances({ a: 0n, b: 0n }))).toEqual({ transfers: [], optimal: true });
    expect(settleUp([])).toEqual({ transfers: [], optimal: true });
  });

  it("settles cancelling pairs directly (2 transfers, not 3)", () => {
    const input = balances({ a: 500n, b: 700n, c: -500n, d: -700n });
    expect(settleUp(input)).toEqual({
      transfers: [
        { from: "c", to: "a", amount: 500n },
        { from: "d", to: "b", amount: 700n },
      ],
      optimal: true,
    });
  });

  it("collapses a chain of debts into one transfer", () => {
    // A owes B 10, B owes C 10 → net A −10, B 0, C +10.
    const input = balances({ a: -1000n, b: 0n, c: 1000n });
    expect(settleUp(input).transfers).toEqual([{ from: "a", to: "c", amount: 1000n }]);
  });

  it("is deterministic", () => {
    const input = balances({ a: 300n, b: -100n, c: 200n, d: -250n, e: -150n });
    expect(settleUp(input)).toEqual(settleUp(input));
  });

  it("rejects balances that do not sum to zero", () => {
    expect(() => settleUp(balances({ a: 1n }))).toThrow();
  });

  it("falls back to greedy above 20 non-zero members", () => {
    const values: Record<string, bigint> = {};
    for (let i = 0; i < 20; i++) values[`m${i}`] = BigInt(i + 1);
    values.m20 = -210n;
    const input = balances(values);
    const plan = settleUp(input);
    expect(plan.optimal).toBe(false);
    expect(plan.transfers.length).toBeLessThanOrEqual(20);
    expectValidPlan(input, plan.transfers);
  });

  it("handles balances too large for safe-integer arithmetic", () => {
    const huge = 10n ** 20n;
    const input = balances({ a: huge, b: -huge, c: 5n, d: -5n });
    const plan = settleUp(input);
    expect(plan.transfers).toHaveLength(2);
    expectValidPlan(input, plan.transfers);
  });

  it("uses the minimum number of transfers (property, vs brute force)", () => {
    const arbBalances = fc
      .array(fc.integer({ min: -5, max: 5 }), { minLength: 1, maxLength: 9 })
      .map((values) => {
        const cents = values.map((v) => BigInt(v) * 100n);
        cents.push(-cents.reduce((a, b) => a + b, 0n));
        return cents.map((balance, i) => ({ memberId: `m${i}`, balance }));
      });
    fc.assert(
      fc.property(arbBalances, (input) => {
        const plan = settleUp(input);
        expectValidPlan(input, plan.transfers);
        const nonZero = input.map((b) => b.balance).filter((b) => b !== 0n);
        expect(plan.optimal).toBe(true);
        expect(plan.transfers).toHaveLength(nonZero.length - bruteMaxGroups(nonZero));
      }),
      { numRuns: 300 },
    );
  });

  it("solves a 20-member worst case in under 1 second", () => {
    const values: Record<string, bigint> = {};
    for (let i = 0; i < 19; i++) values[`m${i}`] = BigInt((i % 2 ? -1 : 1) * (i * 37 + 11));
    const sum = Object.values(values).reduce((a, b) => a + b, 0n);
    values.m19 = -sum;
    const input = balances(values);
    const started = performance.now();
    const plan = settleUp(input);
    const elapsed = performance.now() - started;
    expect(plan.optimal).toBe(true);
    expectValidPlan(input, plan.transfers);
    expect(elapsed).toBeLessThan(1000);
  });
});
