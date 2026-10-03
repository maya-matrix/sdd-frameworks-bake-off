import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { splitEqually } from "../../src/domain/split.js";

const members = ["alice", "bob", "carol"];

function sharesById(shares: { memberId: string; share: bigint }[]) {
  return Object.fromEntries(shares.map((s) => [s.memberId, s.share]));
}

describe("splitEqually", () => {
  it("splits evenly divisible amounts equally", () => {
    expect(sharesById(splitEqually(3000n, members, members))).toEqual({
      alice: 1000n,
      bob: 1000n,
      carol: 1000n,
    });
  });

  it("gives leftover cents to the earliest members", () => {
    expect(sharesById(splitEqually(1000n, members, members))).toEqual({
      alice: 334n,
      bob: 333n,
      carol: 333n,
    });
  });

  it("handles amounts smaller than the participant count", () => {
    expect(sharesById(splitEqually(2n, members, members))).toEqual({
      alice: 1n,
      bob: 1n,
      carol: 0n,
    });
  });

  it("does not depend on the order participants are listed in", () => {
    expect(splitEqually(1000n, ["carol", "bob", "alice"], members)).toEqual(
      splitEqually(1000n, members, members),
    );
  });

  it("only includes listed participants", () => {
    expect(sharesById(splitEqually(2000n, ["bob", "carol"], members))).toEqual({
      bob: 1000n,
      carol: 1000n,
    });
  });

  it("rejects an empty participant list", () => {
    expect(() => splitEqually(100n, [], members)).toThrow();
  });

  it("always sums exactly to the amount with shares differing by at most one cent", () => {
    fc.assert(
      fc.property(
        fc.bigInt({ min: 0n, max: 100_000_000_000n }),
        fc.uniqueArray(fc.integer({ min: 0, max: 49 }), { minLength: 1, maxLength: 50 }),
        (amount, indexes) => {
          const order = Array.from({ length: 50 }, (_, i) => `m${i}`);
          const participants = indexes.map((i) => `m${i}`);
          const shares = splitEqually(amount, participants, order).map((s) => s.share);
          expect(shares.reduce((a, b) => a + b, 0n)).toBe(amount);
          const min = shares.reduce((a, b) => (b < a ? b : a));
          const max = shares.reduce((a, b) => (b > a ? b : a));
          expect(max - min <= 1n).toBe(true);
        },
      ),
    );
  });
});
