import { describe, expect, it } from "vitest";
import fc from "fast-check";
import { splitByPercentage, splitEqually, splitExact } from "../../src/domain/split.js";

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

describe("splitExact", () => {
  it("uses the given amounts as shares", () => {
    expect(
      sharesById(
        splitExact(
          [
            { memberId: "alice", amount: 600n },
            { memberId: "bob", amount: 250n },
            { memberId: "carol", amount: 150n },
          ],
          members,
        ),
      ),
    ).toEqual({ alice: 600n, bob: 250n, carol: 150n });
  });

  it("returns shares in member order regardless of entry order", () => {
    const shares = splitExact(
      [
        { memberId: "carol", amount: 150n },
        { memberId: "alice", amount: 850n },
      ],
      members,
    );
    expect(shares.map((s) => s.memberId)).toEqual(["alice", "carol"]);
  });

  it("keeps zero shares", () => {
    expect(
      sharesById(
        splitExact(
          [
            { memberId: "alice", amount: 1000n },
            { memberId: "bob", amount: 0n },
          ],
          members,
        ),
      ),
    ).toEqual({ alice: 1000n, bob: 0n });
  });

  it("rejects an empty entry list", () => {
    expect(() => splitExact([], members)).toThrow();
  });
});

describe("splitByPercentage", () => {
  const pct = (entries: Record<string, bigint>) =>
    Object.entries(entries).map(([memberId, basisPoints]) => ({ memberId, basisPoints }));

  it("gives the leftover cent to the largest remainder", () => {
    expect(sharesById(splitByPercentage(1000n, pct({ alice: 3333n, bob: 3333n, carol: 3334n }), members))).toEqual({
      alice: 333n,
      bob: 333n,
      carol: 334n,
    });
  });

  it("breaks remainder ties by member order", () => {
    expect(sharesById(splitByPercentage(1n, pct({ alice: 5000n, bob: 5000n }), members))).toEqual({
      alice: 1n,
      bob: 0n,
    });
  });

  it("does not depend on the order entries are listed in", () => {
    expect(sharesById(splitByPercentage(1n, pct({ bob: 5000n, alice: 5000n }), members))).toEqual({
      alice: 1n,
      bob: 0n,
    });
  });

  it("breaks a tie among several participants by member order", () => {
    expect(sharesById(splitByPercentage(2n, pct({ alice: 2500n, bob: 2500n, carol: 5000n }), members))).toEqual({
      alice: 1n,
      bob: 0n,
      carol: 1n,
    });
  });

  it("splits evenly divisible percentages exactly", () => {
    expect(sharesById(splitByPercentage(20000n, pct({ alice: 5000n, bob: 3000n, carol: 2000n }), members))).toEqual({
      alice: 10000n,
      bob: 6000n,
      carol: 4000n,
    });
  });

  it("rejects an empty entry list and percentages not summing to 100", () => {
    expect(() => splitByPercentage(100n, [], members)).toThrow();
    expect(() => splitByPercentage(100n, pct({ alice: 5000n, bob: 4999n }), members)).toThrow();
  });

  /** Random basis-point vectors that sum to exactly 100%. */
  const percentages = fc
    .uniqueArray(fc.integer({ min: 1, max: 9_999 }), { maxLength: 19 })
    .map((cuts) => {
      const points = [0, ...cuts.sort((a, b) => a - b), 10_000];
      return points.slice(1).map((p, i) => BigInt(p - points[i]!));
    });

  it("sums exactly, rounds each share by at most one cent, and ignores entry order", () => {
    const cases = percentages.chain((bps) => {
      const entries = bps.map((basisPoints, i) => ({ memberId: `m${i}`, basisPoints }));
      return fc.tuple(
        fc.constant(entries),
        fc.shuffledSubarray(entries, { minLength: entries.length, maxLength: entries.length }),
      );
    });
    fc.assert(
      fc.property(fc.bigInt({ min: 1n, max: 100_000_000_000n }), cases, (amount, [entries, shuffled]) => {
        const order = entries.map((e) => e.memberId);
        const shares = splitByPercentage(amount, entries, order);
        expect(shares.reduce((sum, s) => sum + s.share, 0n)).toBe(amount);
        shares.forEach((s, i) => {
          const floor = (amount * entries[i]!.basisPoints) / 10_000n;
          expect(s.share === floor || s.share === floor + 1n).toBe(true);
        });
        expect(splitByPercentage(amount, shuffled, order)).toEqual(shares);
      }),
    );
  });
});
