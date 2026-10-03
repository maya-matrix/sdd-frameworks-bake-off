import { beforeEach, describe, expect, it } from "vitest";
import { ConflictError, NotFoundError, ValidationError } from "../../src/domain/errors.js";
import { MemoryStore } from "../../src/store/memoryStore.js";

let store: MemoryStore;

beforeEach(() => {
  store = new MemoryStore();
});

describe("MemoryStore groups and members", () => {
  it("creates a group with trimmed member names in insertion order", () => {
    const group = store.createGroup(" Trip ", ["Alice", " Bob "]);
    expect(group.name).toBe("Trip");
    expect(group.members.map((m) => m.name)).toEqual(["Alice", "Bob"]);
    expect(new Set(group.members.map((m) => m.id)).size).toBe(2);
    expect(store.getGroup(group.id)).toEqual(group);
  });

  it("adds members at the end of the member order", () => {
    const group = store.createGroup("Trip", ["Alice"]);
    const carol = store.addMember(group.id, "Carol");
    expect(store.getGroup(group.id).members).toEqual([group.members[0], carol]);
  });

  it("rejects duplicate names ignoring case and surrounding whitespace", () => {
    const group = store.createGroup("Trip", ["Alice"]);
    expect(() => store.addMember(group.id, " alice ")).toThrow(ConflictError);
    expect(store.getGroup(group.id).members).toHaveLength(1);
    expect(() => store.createGroup("Trip", ["Bob", "BOB"])).toThrow(ConflictError);
  });

  it("rejects blank names", () => {
    expect(() => store.createGroup("   ")).toThrow(ValidationError);
    const group = store.createGroup("Trip");
    expect(() => store.addMember(group.id, "")).toThrow(ValidationError);
  });

  it("throws NotFoundError for unknown groups", () => {
    expect(() => store.getGroup("nope")).toThrow(NotFoundError);
    expect(() => store.addMember("nope", "Alice")).toThrow(NotFoundError);
    expect(() => store.listExpenses("nope")).toThrow(NotFoundError);
  });

  it("does not leak internal state through returned objects", () => {
    const group = store.createGroup("Trip", ["Alice"]);
    group.members.push({ id: "x", name: "Mallory" });
    expect(store.getGroup(group.id).members).toHaveLength(1);
  });
});

describe("MemoryStore expenses", () => {
  it("records expenses with stored shares and lists them in order", () => {
    const group = store.createGroup("Trip", ["Alice", "Bob", "Carol"]);
    const [a, b, c] = group.members.map((m) => m.id) as [string, string, string];
    const first = store.recordExpense(group.id, {
      payerId: a,
      amount: 1000n,
      description: "Taxi",
      splitBetween: [c, b, a],
    });
    expect(first.shares).toEqual([
      { memberId: a, share: 334n },
      { memberId: b, share: 333n },
      { memberId: c, share: 333n },
    ]);
    expect(first.createdAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    const second = store.recordExpense(group.id, {
      payerId: b,
      amount: 500n,
      description: "Snacks",
      splitBetween: [a],
    });
    expect(store.listExpenses(group.id).map((e) => e.id)).toEqual([first.id, second.id]);
  });

  it("validates before recording anything", () => {
    const group = store.createGroup("Trip", ["Alice", "Bob"]);
    const other = store.createGroup("Other", ["Eve"]);
    const [a, b] = group.members.map((m) => m.id) as [string, string];
    const eve = other.members[0]!.id;
    const base = { payerId: a, amount: 100n, description: "x", splitBetween: [a, b] };
    for (const bad of [
      { ...base, amount: 0n },
      { ...base, amount: 100_000_000_001n },
      { ...base, description: "  " },
      { ...base, payerId: eve },
      { ...base, splitBetween: [] },
      { ...base, splitBetween: [a, a] },
      { ...base, splitBetween: [a, eve] },
    ]) {
      expect(() => store.recordExpense(group.id, bad)).toThrow(ValidationError);
    }
    expect(store.listExpenses(group.id)).toEqual([]);
    expect(() => store.recordExpense(group.id, { ...base, amount: 100_000_000_000n })).not.toThrow();
  });
});
