import { beforeEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { parseAmount } from "../../src/domain/money.js";
import { balancesByName, createGroup, newApp, recordExpense, type TestGroup } from "./helpers.js";

let app: FastifyInstance;
let group: TestGroup;

beforeEach(async () => {
  app = newApp();
  group = await createGroup(app, ["Alice", "Bob", "Carol", "Dave"]);
});

/** Exact sum of decimal-string balances, via cents. */
function sumCents(values: string[]): bigint {
  return values.reduce((sum, v) => sum + (v.startsWith("-") ? -parseAmount(v.slice(1)) : parseAmount(v)), 0n);
}

describe("GET /groups/:groupId/balances", () => {
  it("returns every member with id, name and balance in member order", async () => {
    const response = await app.inject({ method: "GET", url: `/groups/${group.id}/balances` });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({
      balances: ["Alice", "Bob", "Carol", "Dave"].map((name) => ({
        memberId: group.ids[name],
        name,
        balance: "0.00",
      })),
    });
  });

  it("reflects a single expense", async () => {
    await recordExpense(app, group, "Alice", "30.00", ["Alice", "Bob", "Carol"]);
    expect(await balancesByName(app, group.id)).toEqual({
      Alice: "20.00",
      Bob: "-10.00",
      Carol: "-10.00",
      Dave: "0.00",
    });
  });

  it("accumulates multiple expenses", async () => {
    await recordExpense(app, group, "Alice", "30.00", ["Alice", "Bob", "Carol"]);
    await recordExpense(app, group, "Bob", "12.00", ["Alice", "Bob"]);
    expect(await balancesByName(app, group.id)).toEqual({
      Alice: "14.00",
      Bob: "-4.00",
      Carol: "-10.00",
      Dave: "0.00",
    });
  });

  it("stays exact and sums to zero across repeated uneven splits", async () => {
    for (let i = 0; i < 3; i++) {
      await recordExpense(app, group, "Alice", "10.00", ["Alice", "Bob", "Carol"]);
    }
    const balances = await balancesByName(app, group.id);
    expect(balances).toEqual({ Alice: "19.98", Bob: "-9.99", Carol: "-9.99", Dave: "0.00" });
    expect(sumCents(Object.values(balances))).toBe(0n);
  });

  it("keeps 0.10 + 0.20 exact", async () => {
    await recordExpense(app, group, "Alice", "0.10", ["Alice", "Bob"]);
    await recordExpense(app, group, "Alice", "0.20", ["Alice", "Bob"]);
    expect(await balancesByName(app, group.id)).toMatchObject({ Alice: "0.15", Bob: "-0.15" });
  });

  it("always sums to exactly zero over many uneven expenses", async () => {
    const amounts = ["0.01", "0.07", "1.00", "9.99", "100.01", "33.33", "0.05"];
    const names = ["Alice", "Bob", "Carol", "Dave"];
    for (const [i, amount] of amounts.entries()) {
      const payer = names[i % names.length]!;
      const participants = names.slice(0, (i % 3) + 2);
      await recordExpense(app, group, payer, amount, participants);
    }
    expect(sumCents(Object.values(await balancesByName(app, group.id)))).toBe(0n);
  });

  it("returns 404 for an unknown group", async () => {
    const response = await app.inject({
      method: "GET",
      url: "/groups/00000000-0000-4000-8000-000000000000/balances",
    });
    expect(response.statusCode).toBe(404);
  });
});
