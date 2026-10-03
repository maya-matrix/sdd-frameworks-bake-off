import { FULL_PERCENTAGE, type BasisPoints, type Cents } from "./money.js";

export interface Share {
  memberId: string;
  share: Cents;
}

/**
 * Splits `amount` equally between participants. Shares differ by at most one
 * cent and always sum exactly to `amount`. Leftover cents go one each to the
 * participants that come first in `memberOrder` (the group's member order),
 * so the result does not depend on the order participants were listed in.
 *
 * Returned shares are in member order.
 */
export function splitEqually(
  amount: Cents,
  participantIds: readonly string[],
  memberOrder: readonly string[],
): Share[] {
  if (participantIds.length === 0) {
    throw new Error("Cannot split between zero participants");
  }
  const rank = new Map(memberOrder.map((id, index) => [id, index]));
  const ordered = [...participantIds].sort(
    (a, b) => (rank.get(a) ?? Infinity) - (rank.get(b) ?? Infinity),
  );
  const n = BigInt(ordered.length);
  const base = amount / n;
  const remainder = amount % n;
  return ordered.map((memberId, index) => ({
    memberId,
    share: base + (BigInt(index) < remainder ? 1n : 0n),
  }));
}

export interface ExactSplitEntry {
  memberId: string;
  amount: Cents;
}

export interface PercentageSplitEntry {
  memberId: string;
  basisPoints: BasisPoints;
}

/**
 * Uses the given amounts as shares. The caller must have checked that they
 * sum to the expense amount. Returned shares are in member order.
 */
export function splitExact(
  entries: readonly ExactSplitEntry[],
  memberOrder: readonly string[],
): Share[] {
  if (entries.length === 0) {
    throw new Error("Cannot split between zero participants");
  }
  return inMemberOrder(entries, memberOrder).map(({ memberId, amount }) => ({ memberId, share: amount }));
}

/**
 * Splits `amount` by percentages (in basis points summing to 100%) using the
 * largest-remainder method: every share is first rounded down, then the
 * leftover cents go one each to the participants whose discarded fractions
 * are largest, ties going to the participant that comes first in
 * `memberOrder`. Shares always sum exactly to `amount` and do not depend on
 * the order entries were listed in.
 *
 * Returned shares are in member order.
 */
export function splitByPercentage(
  amount: Cents,
  entries: readonly PercentageSplitEntry[],
  memberOrder: readonly string[],
): Share[] {
  if (entries.length === 0) {
    throw new Error("Cannot split between zero participants");
  }
  const total = entries.reduce((sum, e) => sum + e.basisPoints, 0n);
  if (total !== FULL_PERCENTAGE) {
    throw new Error(`Percentages must sum to 100, got ${total} basis points`);
  }
  const ordered = inMemberOrder(entries, memberOrder).map(({ memberId, basisPoints }) => {
    const product = amount * basisPoints;
    return { memberId, share: product / FULL_PERCENTAGE, remainder: product % FULL_PERCENTAGE };
  });
  let leftover = amount - ordered.reduce((sum, s) => sum + s.share, 0n);
  // Stable sort keeps member order among equal remainders.
  const byRemainder = [...ordered].sort((a, b) =>
    a.remainder === b.remainder ? 0 : a.remainder > b.remainder ? -1 : 1,
  );
  for (const entry of byRemainder) {
    if (leftover === 0n) break;
    entry.share += 1n;
    leftover -= 1n;
  }
  return ordered.map(({ memberId, share }) => ({ memberId, share }));
}

function inMemberOrder<T extends { memberId: string }>(entries: readonly T[], memberOrder: readonly string[]): T[] {
  const rank = new Map(memberOrder.map((id, index) => [id, index]));
  return [...entries].sort((a, b) => (rank.get(a.memberId) ?? Infinity) - (rank.get(b.memberId) ?? Infinity));
}
