import { beforeEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { parseAmount } from "../../src/domain/money.js";
import { createGroup, newApp, recordExpense, type TestGroup } from "./helpers.js";

interface TransferBody {
  from: string;
  to: string;
  amount: string;
}

let app: FastifyInstance;

beforeEach(() => {
  app = newApp();
});

const toCents = (v: string) => (v.startsWith("-") ? -parseAmount(v.slice(1)) : parseAmount(v));

async function settleUp(groupId: string) {
  const response = await app.inject({ method: "GET", url: `/groups/${groupId}/settle-up` });
  return { status: response.statusCode, body: response.json() as { transfers: TransferBody[]; optimal: boolean } };
}

/** Applies the settle-up plan to the reported balances and checks everything reaches exactly zero. */
async function expectPlanClearsBalances(groupId: string) {
  const balances = (await app.inject({ method: "GET", url: `/groups/${groupId}/balances` })).json() as {
    balances: { memberId: string; balance: string }[];
  };
  const remaining = new Map(balances.balances.map((b) => [b.memberId, toCents(b.balance)]));
  const { body } = await settleUp(groupId);
  for (const t of body.transfers) {
    expect(toCents(t.amount) > 0n).toBe(true);
    expect(t.from).not.toBe(t.to);
    remaining.set(t.from, remaining.get(t.from)! + toCents(t.amount));
    remaining.set(t.to, remaining.get(t.to)! - toCents(t.amount));
  }
  for (const value of remaining.values()) {
    expect(value).toBe(0n);
  }
  return body;
}

describe("GET /groups/:groupId/settle-up", () => {
  let group: TestGroup;

  beforeEach(async () => {
    group = await createGroup(app, ["Alice", "Bob", "Carol", "Dave"]);
  });

  it("settles a simple debt", async () => {
    await recordExpense(app, group, "Alice", "30.00", ["Alice", "Bob", "Carol"]);
    const { status, body } = await settleUp(group.id);
    expect(status).toBe(200);
    expect(body).toEqual({
      transfers: [
        { from: group.ids.Bob, to: group.ids.Alice, amount: "10.00" },
        { from: group.ids.Carol, to: group.ids.Alice, amount: "10.00" },
      ],
      optimal: true,
    });
  });

  it("returns no transfers for a group with no expenses", async () => {
    expect((await settleUp(group.id)).body).toEqual({ transfers: [], optimal: true });
  });

  it("returns no transfers when balances net to zero", async () => {
    await recordExpense(app, group, "Alice", "10.00", ["Bob"]);
    await recordExpense(app, group, "Bob", "10.00", ["Alice"]);
    expect((await settleUp(group.id)).body.transfers).toEqual([]);
  });

  it("settles cancelling pairs directly in 2 transfers", async () => {
    // Balances: Alice +5, Bob +7, Carol −5, Dave −7.
    await recordExpense(app, group, "Alice", "5.00", ["Carol"]);
    await recordExpense(app, group, "Bob", "7.00", ["Dave"]);
    const body = await expectPlanClearsBalances(group.id);
    expect(body).toEqual({
      transfers: [
        { from: group.ids.Carol, to: group.ids.Alice, amount: "5.00" },
        { from: group.ids.Dave, to: group.ids.Bob, amount: "7.00" },
      ],
      optimal: true,
    });
  });

  it("collapses a chain of debts into a single transfer", async () => {
    // Bob pays for Alice; Carol pays for Bob → Alice owes Carol.
    await recordExpense(app, group, "Bob", "10.00", ["Alice"]);
    await recordExpense(app, group, "Carol", "10.00", ["Bob"]);
    expect((await settleUp(group.id)).body.transfers).toEqual([
      { from: group.ids.Alice, to: group.ids.Carol, amount: "10.00" },
    ]);
  });

  it("is deterministic", async () => {
    await recordExpense(app, group, "Alice", "17.03", ["Alice", "Bob", "Carol", "Dave"]);
    await recordExpense(app, group, "Carol", "4.10", ["Bob", "Dave"]);
    expect((await settleUp(group.id)).body).toEqual((await settleUp(group.id)).body);
  });

  it("produces a plan that clears the reported balances after many uneven expenses", async () => {
    const names = ["Alice", "Bob", "Carol", "Dave"];
    const amounts = ["10.00", "0.01", "3.33", "7.77", "100.00", "0.10", "0.20", "55.55"];
    for (const [i, amount] of amounts.entries()) {
      await recordExpense(app, group, names[(i * 3) % 4]!, amount, names.filter((_, j) => (i + j) % 3 !== 0));
    }
    const body = await expectPlanClearsBalances(group.id);
    expect(body.optimal).toBe(true);
    expect(body.transfers.length).toBeLessThanOrEqual(3);
  });

  it("returns 404 for an unknown group", async () => {
    expect((await settleUp("00000000-0000-4000-8000-000000000000")).status).toBe(404);
  });
});
