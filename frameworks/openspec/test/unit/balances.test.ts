import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { computeBalances, type ExpenseEntry } from "../../src/domain/balances.js";
import { formatAmount, parseAmount } from "../../src/domain/money.js";
import { splitEqually } from "../../src/domain/split.js";

const members = ["alice", "bob", "carol", "dave"];

function expense(payerId: string, amount: string, participants: string[]): ExpenseEntry {
  const cents = parseAmount(amount);
  return { payerId, amount: cents, shares: splitEqually(cents, participants, members) };
}

function formatted(expenses: ExpenseEntry[]) {
  return Object.fromEntries(
    computeBalances(members, expenses).map((b) => [b.memberId, formatAmount(b.balance)]),
  );
}

describe("computeBalances", () => {
  it("handles a single expense", () => {
    expect(formatted([expense("alice", "30.00", ["alice", "bob", "carol"])])).toEqual({
      alice: "20.00",
      bob: "-10.00",
      carol: "-10.00",
      dave: "0.00",
    });
  });

  it("accumulates multiple expenses", () => {
    expect(
      formatted([
        expense("alice", "30.00", ["alice", "bob", "carol"]),
        expense("bob", "12.00", ["alice", "bob"]),
      ]),
    ).toEqual({ alice: "14.00", bob: "-4.00", carol: "-10.00", dave: "0.00" });
  });

  it("stays exact across repeated uneven splits", () => {
    const e = expense("alice", "10.00", ["alice", "bob", "carol"]);
    expect(formatted([e, e, e])).toEqual({
      alice: "19.98",
      bob: "-9.99",
      carol: "-9.99",
      dave: "0.00",
    });
  });

  it("keeps floating-point-prone values exact", () => {
    expect(
      formatted([expense("alice", "0.10", ["alice", "bob"]), expense("alice", "0.20", ["alice", "bob"])]),
    ).toMatchObject({ alice: "0.15", bob: "-0.15" });
  });

  it("returns members in member order, including inactive ones", () => {
    expect(computeBalances(members, []).map((b) => b.memberId)).toEqual(members);
  });

  it("always sums to exactly zero", () => {
    const arbExpense = fc.record({
      payer: fc.constantFrom(...members),
      amount: fc.bigInt({ min: 1n, max: 100_000_000_000n }),
      participants: fc.subarray(members, { minLength: 1 }),
    });
    fc.assert(
      fc.property(fc.array(arbExpense, { maxLength: 30 }), (raw) => {
        const expenses = raw.map((e) => ({
          payerId: e.payer,
          amount: e.amount,
          shares: splitEqually(e.amount, e.participants, members),
        }));
        const total = computeBalances(members, expenses).reduce((s, b) => s + b.balance, 0n);
        expect(total).toBe(0n);
      }),
    );
  });
});
