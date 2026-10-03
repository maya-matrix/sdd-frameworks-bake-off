import { beforeEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { balancesByName, createGroup, newApp, postExpense, recordExpense, type TestGroup } from "./helpers.js";

let app: FastifyInstance;
let group: TestGroup;

beforeEach(async () => {
  app = newApp();
  group = await createGroup(app, ["Alice", "Bob", "Carol"]);
});

function shareOf(expense: { shares: { memberId: string; share: string }[] }, name: string) {
  return expense.shares.find((s) => s.memberId === group.ids[name])?.share;
}

async function listExpenses(groupId = group.id) {
  return app.inject({ method: "GET", url: `/groups/${groupId}/expenses` });
}

describe("POST /groups/:groupId/expenses", () => {
  it("records an evenly divisible expense", async () => {
    const response = await postExpense(app, group.id, {
      payerId: group.ids.Alice,
      amount: "30.00",
      description: "Dinner",
      splitBetween: [group.ids.Alice, group.ids.Bob, group.ids.Carol],
    });
    expect(response.statusCode).toBe(201);
    const expense = response.json();
    expect(expense).toMatchObject({
      id: expect.any(String),
      payerId: group.ids.Alice,
      amount: "30.00",
      description: "Dinner",
      splitBetween: [group.ids.Alice, group.ids.Bob, group.ids.Carol],
      createdAt: expect.any(String),
    });
    for (const name of ["Alice", "Bob", "Carol"]) {
      expect(shareOf(expense, name)).toBe("10.00");
    }
  });

  it("does not give the payer a share when they are not a participant", async () => {
    const expense = await recordExpense(app, group, "Alice", "20.00", ["Bob", "Carol"]);
    expect(shareOf(expense, "Bob")).toBe("10.00");
    expect(shareOf(expense, "Carol")).toBe("10.00");
    expect(shareOf(expense, "Alice")).toBeUndefined();
  });

  it("returns 404 for an unknown group", async () => {
    const response = await postExpense(app, "00000000-0000-4000-8000-000000000000", {
      payerId: group.ids.Alice,
      amount: "1.00",
      description: "x",
      splitBetween: [group.ids.Alice],
    });
    expect(response.statusCode).toBe(404);
  });

  it("normalizes the amount format", async () => {
    const expense = await recordExpense(app, group, "Alice", "7.5", ["Alice"]);
    expect(expense.amount).toBe("7.50");
  });

  it("splits unevenly with remainder cents to earliest members", async () => {
    const expense = await recordExpense(app, group, "Alice", "10.00", ["Alice", "Bob", "Carol"]);
    expect([shareOf(expense, "Alice"), shareOf(expense, "Bob"), shareOf(expense, "Carol")]).toEqual([
      "3.34",
      "3.33",
      "3.33",
    ]);
  });

  it("allocates remainders independently of request order", async () => {
    const expense = await recordExpense(app, group, "Alice", "10.00", ["Carol", "Bob", "Alice"]);
    expect(shareOf(expense, "Alice")).toBe("3.34");
    expect(shareOf(expense, "Bob")).toBe("3.33");
    expect(shareOf(expense, "Carol")).toBe("3.33");
  });

  it("handles an amount smaller than the participant count", async () => {
    const expense = await recordExpense(app, group, "Alice", "0.02", ["Alice", "Bob", "Carol"]);
    expect([shareOf(expense, "Alice"), shareOf(expense, "Bob"), shareOf(expense, "Carol")]).toEqual([
      "0.01",
      "0.01",
      "0.00",
    ]);
  });

  it("keeps floating-point-prone values exact", async () => {
    await recordExpense(app, group, "Alice", "0.10", ["Alice", "Bob"]);
    await recordExpense(app, group, "Alice", "0.20", ["Alice", "Bob"]);
    expect(await balancesByName(app, group.id)).toMatchObject({ Alice: "0.15", Bob: "-0.15" });
  });

  describe("validation", () => {
    const valid = () => ({
      payerId: group.ids.Alice,
      amount: "10.00",
      description: "Lunch",
      splitBetween: [group.ids.Alice, group.ids.Bob],
    });

    it.each<[string, (body: Record<string, unknown>) => void]>([
      ["amount as a JSON number", (b) => (b.amount = 12.5)],
      ["too many fraction digits", (b) => (b.amount = "10.005")],
      ["negative amount", (b) => (b.amount = "-5.00")],
      ["zero amount", (b) => (b.amount = "0.00")],
      ["amount above the maximum", (b) => (b.amount = "1000000000.01")],
      ["non-numeric amount", (b) => (b.amount = "ten")],
      ["missing amount", (b) => delete b.amount],
      ["blank description", (b) => (b.description = "   ")],
      ["missing description", (b) => delete b.description],
      ["empty split list", (b) => (b.splitBetween = [])],
      ["missing split list", (b) => delete b.splitBetween],
      ["duplicate participants", (b) => (b.splitBetween = [group.ids.Alice, group.ids.Alice])],
      ["payer not a member", (b) => (b.payerId = "00000000-0000-4000-8000-000000000000")],
      ["participant not a member", (b) => (b.splitBetween = [group.ids.Alice, "someone-else"])],
    ])("rejects %s with 400 and records nothing", async (_label, mutate) => {
      const body: Record<string, unknown> = valid();
      mutate(body);
      const response = await postExpense(app, group.id, body);
      expect(response.statusCode).toBe(400);
      expect(response.json().error.code).toBe("VALIDATION_ERROR");
      expect((await listExpenses()).json().expenses).toEqual([]);
    });

    it("rejects a participant who belongs to a different group", async () => {
      const other = await createGroup(app, ["Eve"], "Other");
      const response = await postExpense(app, group.id, { ...valid(), splitBetween: [group.ids.Alice, other.ids.Eve] });
      expect(response.statusCode).toBe(400);
      expect((await listExpenses()).json().expenses).toEqual([]);
    });

    it("rejects a payer who belongs to a different group", async () => {
      const other = await createGroup(app, ["Eve"], "Other");
      const response = await postExpense(app, group.id, { ...valid(), payerId: other.ids.Eve });
      expect(response.statusCode).toBe(400);
      expect((await listExpenses()).json().expenses).toEqual([]);
    });

    it("accepts the maximum amount", async () => {
      const response = await postExpense(app, group.id, { ...valid(), amount: "1000000000.00" });
      expect(response.statusCode).toBe(201);
    });
  });
});

describe("GET /groups/:groupId/expenses", () => {
  it("lists expenses in recording order", async () => {
    const first = await recordExpense(app, group, "Alice", "30.00", ["Alice", "Bob", "Carol"], "Dinner");
    const second = await recordExpense(app, group, "Bob", "12.00", ["Alice", "Bob"], "Taxi");
    const response = await listExpenses();
    expect(response.statusCode).toBe(200);
    expect(response.json().expenses).toEqual([first, second]);
  });

  it("returns an empty list when there are no expenses", async () => {
    const response = await listExpenses();
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual({ expenses: [] });
  });

  it("returns 404 for an unknown group", async () => {
    const response = await listExpenses("00000000-0000-4000-8000-000000000000");
    expect(response.statusCode).toBe(404);
  });
});

describe("unequal splits", () => {
  const exactBody = (splits: Record<string, string | number>, amount = "10.00") => ({
    payerId: group.ids.Alice,
    amount,
    description: "Dinner",
    splitType: "exact",
    splits: Object.entries(splits).map(([name, value]) => ({ memberId: group.ids[name] ?? name, amount: value })),
  });
  const percentageBody = (splits: Record<string, string | number>, amount = "10.00") => ({
    payerId: group.ids.Alice,
    amount,
    description: "Dinner",
    splitType: "percentage",
    splits: Object.entries(splits).map(([name, value]) => ({ memberId: group.ids[name] ?? name, percentage: value })),
  });
  const sharesByName = (expense: { shares: { memberId: string; share: string }[] }) =>
    Object.fromEntries(
      expense.shares.map((s) => [Object.keys(group.ids).find((n) => group.ids[n] === s.memberId), s.share]),
    );

  async function expectRejected(body: unknown) {
    const response = await postExpense(app, group.id, body);
    expect(response.statusCode).toBe(400);
    expect(response.json().error.code).toBe("VALIDATION_ERROR");
    expect((await listExpenses()).json().expenses).toEqual([]);
  }

  it("keeps the equal-split response unchanged apart from splitType", async () => {
    const expense = await recordExpense(app, group, "Alice", "10.00", ["Alice", "Bob", "Carol"]);
    expect(Object.keys(expense).sort()).toEqual(
      ["amount", "createdAt", "description", "groupId", "id", "payerId", "shares", "splitBetween", "splitType"],
    );
    expect(expense.splitType).toBe("equal");
  });

  it("treats an explicit equal split type like the default", async () => {
    const response = await postExpense(app, group.id, {
      payerId: group.ids.Alice,
      amount: "10.00",
      description: "Taxi",
      splitType: "equal",
      splitBetween: [group.ids.Carol, group.ids.Bob, group.ids.Alice],
    });
    expect(response.statusCode).toBe(201);
    expect(sharesByName(response.json())).toEqual({ Alice: "3.34", Bob: "3.33", Carol: "3.33" });
  });

  it("rejects an unknown split type", async () => {
    await expectRejected({ ...exactBody({ Alice: "10.00" }), splitType: "shares" });
  });

  describe("exact", () => {
    it("records exact amounts that sum to the total", async () => {
      const response = await postExpense(app, group.id, exactBody({ Alice: "6.00", Bob: "2.50", Carol: "1.50" }));
      expect(response.statusCode).toBe(201);
      expect(sharesByName(response.json())).toEqual({ Alice: "6.00", Bob: "2.50", Carol: "1.50" });
    });

    it("keeps a zero share", async () => {
      const response = await postExpense(app, group.id, exactBody({ Alice: "10.00", Bob: "0" }));
      expect(response.statusCode).toBe(201);
      expect(sharesByName(response.json())).toEqual({ Alice: "10.00", Bob: "0.00" });
    });

    it.each<[string, Record<string, string | number>]>([
      ["amounts below the total", { Alice: "6.00", Bob: "3.99" }],
      ["amounts above the total", { Alice: "6.00", Bob: "4.01" }],
      ["an amount as a JSON number", { Alice: "5.00", Bob: 5 }],
      ["too many fraction digits", { Alice: "4.995", Bob: "5.005" }],
      ["a negative amount", { Alice: "11.00", Bob: "-1.00" }],
      ["a non-member", { Alice: "6.00", "someone-else": "4.00" }],
    ])("rejects %s", async (_label, splits) => {
      await expectRejected(exactBody(splits));
    });
  });

  describe("percentage", () => {
    it("records percentages that sum to 100", async () => {
      const response = await postExpense(app, group.id, percentageBody({ Alice: "50", Bob: "30", Carol: "20" }, "200.00"));
      expect(response.statusCode).toBe(201);
      expect(sharesByName(response.json())).toEqual({ Alice: "100.00", Bob: "60.00", Carol: "40.00" });
    });

    it("gives the leftover cent to the largest remainder", async () => {
      const response = await postExpense(app, group.id, percentageBody({ Alice: "33.33", Bob: "33.33", Carol: "33.34" }));
      expect(response.statusCode).toBe(201);
      expect(sharesByName(response.json())).toEqual({ Alice: "3.33", Bob: "3.33", Carol: "3.34" });
    });

    it.each([
      ["Alice first", { Alice: "50", Bob: "50" }],
      ["Bob first", { Bob: "50", Alice: "50" }],
    ])("breaks remainder ties by member order (%s)", async (_label, splits) => {
      const response = await postExpense(app, group.id, percentageBody(splits, "0.01"));
      expect(response.statusCode).toBe(201);
      expect(sharesByName(response.json())).toEqual({ Alice: "0.01", Bob: "0.00" });
    });

    it("breaks a tie among several participants by member order", async () => {
      const response = await postExpense(app, group.id, percentageBody({ Alice: "25", Bob: "25", Carol: "50" }, "0.02"));
      expect(sharesByName(response.json())).toEqual({ Alice: "0.01", Bob: "0.00", Carol: "0.01" });
    });

    it.each<[string, Record<string, string | number>]>([
      ["percentages below 100", { Alice: "50", Bob: "49.99" }],
      ["percentages above 100", { Alice: "60", Bob: "40.01" }],
      ["a percentage above 100", { Alice: "100.01", Bob: "0" }],
      ["a negative percentage", { Alice: "105", Bob: "-5" }],
      ["a percentage as a JSON number", { Alice: "50", Bob: 50 }],
      ["too many fraction digits", { Alice: "66.667", Bob: "33.333" }],
    ])("rejects %s", async (_label, splits) => {
      await expectRejected(percentageBody(splits));
    });

    it("echoes normalized splits and derives splitBetween", async () => {
      const response = await postExpense(app, group.id, percentageBody({ Alice: "60", Bob: "40" }));
      expect(response.json()).toMatchObject({
        splitType: "percentage",
        splitBetween: [group.ids.Alice, group.ids.Bob],
        splits: [
          { memberId: group.ids.Alice, percentage: "60.00" },
          { memberId: group.ids.Bob, percentage: "40.00" },
        ],
      });
    });
  });

  it.each<[string, () => unknown]>([
    ["missing splits", () => ({ ...exactBody({}), splits: undefined })],
    ["empty splits", () => exactBody({})],
    ["both splitBetween and splits", () => ({ ...exactBody({ Alice: "10.00" }), splitBetween: [group.ids.Alice] })],
    [
      "splits with an equal split",
      () => ({ ...exactBody({ Alice: "10.00" }), splitType: "equal", splitBetween: [group.ids.Alice] }),
    ],
    [
      "a duplicate member",
      () => ({
        ...percentageBody({}),
        splits: [
          { memberId: group.ids.Alice, percentage: "50" },
          { memberId: group.ids.Alice, percentage: "50" },
        ],
      }),
    ],
    ["a percentage in an exact split", () => ({ ...exactBody({}), splits: [{ memberId: group.ids.Alice, percentage: "100" }] })],
    ["an amount in a percentage split", () => ({ ...percentageBody({}), splits: [{ memberId: group.ids.Alice, amount: "10.00" }] })],
  ])("rejects %s", async (_label, body) => {
    await expectRejected(body());
  });

  it("lists mixed split types with their own details", async () => {
    await recordExpense(app, group, "Alice", "30.00", ["Alice", "Bob", "Carol"]);
    await postExpense(app, group.id, percentageBody({ Alice: "60", Bob: "40" }));
    const [equal, percentage] = (await listExpenses()).json().expenses;
    expect(equal.splitType).toBe("equal");
    expect(equal).not.toHaveProperty("splits");
    expect(percentage.splitType).toBe("percentage");
    expect(percentage.splits).toHaveLength(2);
  });
});
