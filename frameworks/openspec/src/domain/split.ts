import type { Cents } from "./money.js";

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
