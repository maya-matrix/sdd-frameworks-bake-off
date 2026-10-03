import type { Balance } from "./balances.js";
import type { Cents } from "./money.js";

export interface Transfer {
  from: string;
  to: string;
  amount: Cents;
}

export interface SettlePlan {
  transfers: Transfer[];
  /** True when the plan is guaranteed to use the fewest possible transfers. */
  optimal: boolean;
}

/** Largest number of non-zero balances for which an exact minimum is computed. */
export const MAX_EXACT_MEMBERS = 20;

export interface Party {
  memberId: string;
  /** Position in the group's member order; used to break ties deterministically. */
  rank: number;
  balance: Cents;
}

/**
 * Produces transfers that bring every balance to zero. Balances must be given
 * in member order and sum to zero.
 *
 * The minimum number of transfers is n − k, where n is the number of non-zero
 * balances and k is the largest number of disjoint zero-sum groups they can be
 * partitioned into. For n ≤ MAX_EXACT_MEMBERS that partition is found exactly
 * with a bitmask DP; each group is then settled greedily in (size − 1)
 * transfers. Above the threshold, the whole set is settled greedily.
 */
export function settleUp(balances: readonly Balance[]): SettlePlan {
  const total = balances.reduce((sum, b) => sum + b.balance, 0n);
  if (total !== 0n) {
    throw new Error("Balances must sum to zero");
  }
  const parties: Party[] = balances
    .map((b, rank) => ({ memberId: b.memberId, rank, balance: b.balance }))
    .filter((p) => p.balance !== 0n);

  const optimal = parties.length <= MAX_EXACT_MEMBERS;
  const groups = optimal ? maxZeroSumPartition(parties) : [parties];
  const transfers = groups.flatMap(settleGreedily);

  const rankOf = new Map(parties.map((p) => [p.memberId, p.rank]));
  transfers.sort(
    (a, b) =>
      rankOf.get(a.from)! - rankOf.get(b.from)! || rankOf.get(a.to)! - rankOf.get(b.to)!,
  );
  return { transfers, optimal };
}

/**
 * Settles a zero-sum group by repeatedly matching the largest debtor with the
 * largest creditor. Each step zeroes at least one party, so a group of size s
 * needs at most s − 1 transfers; debtors only send and creditors only receive.
 */
export function settleGreedily(group: readonly Party[]): Transfer[] {
  const debtors = group.filter((p) => p.balance < 0n).map((p) => ({ ...p, open: -p.balance }));
  const creditors = group.filter((p) => p.balance > 0n).map((p) => ({ ...p, open: p.balance }));
  const byLargest = (a: { open: Cents; rank: number }, b: { open: Cents; rank: number }) =>
    a.open === b.open ? a.rank - b.rank : a.open > b.open ? -1 : 1;

  const transfers: Transfer[] = [];
  for (;;) {
    debtors.sort(byLargest);
    creditors.sort(byLargest);
    const debtor = debtors[0];
    const creditor = creditors[0];
    if (!debtor || !creditor || debtor.open === 0n || creditor.open === 0n) {
      break;
    }
    const amount = debtor.open < creditor.open ? debtor.open : creditor.open;
    transfers.push({ from: debtor.memberId, to: creditor.memberId, amount });
    debtor.open -= amount;
    creditor.open -= amount;
  }
  return transfers;
}

/**
 * Partitions parties into the maximum number of disjoint zero-sum groups.
 * dp[mask] = max number of zero-sum groups `mask` can be split into, computed
 * as max over i ∈ mask of dp[mask \ i], plus one when mask itself sums to zero.
 */
function maxZeroSumPartition(parties: readonly Party[]): Party[][] {
  const n = parties.length;
  if (n === 0) {
    return [];
  }
  const size = 1 << n;
  const isZero = zeroSumTable(parties.map((p) => p.balance));

  const dp = new Uint8Array(size);
  for (let mask = 1; mask < size; mask++) {
    let best = 0;
    for (let i = 0; i < n; i++) {
      const bit = 1 << i;
      if (mask & bit) {
        const candidate = dp[mask ^ bit]!;
        if (candidate > best) best = candidate;
      }
    }
    dp[mask] = best + (isZero[mask] ? 1 : 0);
  }

  // Walk back from the full set, removing one party at a time along an optimal
  // path. The parties removed between two consecutive zero-sum masks form a group.
  const groups: Party[][] = [];
  let current: Party[] = [];
  let mask = size - 1;
  while (mask !== 0) {
    const target = dp[mask]! - (isZero[mask] ? 1 : 0);
    let i = 0;
    while (!((mask >> i) & 1) || dp[mask ^ (1 << i)] !== target) {
      i++;
    }
    current.push(parties[i]!);
    mask ^= 1 << i;
    if (mask === 0 || isZero[mask]) {
      groups.push(current);
      current = [];
    }
  }
  return groups;
}

/** isZero[mask] is 1 when the balances selected by `mask` sum to exactly zero. */
function zeroSumTable(balances: readonly Cents[]): Uint8Array {
  const n = balances.length;
  const size = 1 << n;
  const isZero = new Uint8Array(size);
  const absTotal = balances.reduce((sum, b) => sum + (b < 0n ? -b : b), 0n);

  if (absTotal <= BigInt(Number.MAX_SAFE_INTEGER)) {
    // Every subset sum is a safe integer, so number arithmetic is exact here.
    const values = balances.map(Number);
    const sums = new Float64Array(size);
    for (let mask = 1; mask < size; mask++) {
      const low = 31 - Math.clz32(mask & -mask);
      sums[mask] = sums[mask & (mask - 1)]! + values[low]!;
      isZero[mask] = sums[mask] === 0 ? 1 : 0;
    }
  } else {
    const sums: bigint[] = new Array<bigint>(size).fill(0n);
    for (let mask = 1; mask < size; mask++) {
      const low = 31 - Math.clz32(mask & -mask);
      sums[mask] = sums[mask & (mask - 1)]! + balances[low]!;
      isZero[mask] = sums[mask] === 0n ? 1 : 0;
    }
  }
  return isZero;
}
