import type { Balance, SettlementPlan, Transfer } from './types.js';

/** Above this many non-zero balances the exact DP is skipped in favour of greedy. */
export const MAX_EXACT_PARTICIPANTS = 16;

/**
 * Suggests transfers that zero every balance. Input order is the tie-break order.
 * With ≤ MAX_EXACT_PARTICIPANTS non-zero balances the transfer count is the proven minimum
 * (non-zero count − maximum number of disjoint zero-sum subgroups) and optimal is true;
 * beyond that a greedy plan is returned with optimal false. Every transfer amount is > 0.
 */
export function suggestTransfers(balances: Balance[]): SettlementPlan {
  const nonZero = balances.filter((b) => b.net !== 0n);
  if (nonZero.length === 0) {
    return { transfers: [], optimal: true };
  }
  if (nonZero.length > MAX_EXACT_PARTICIPANTS) {
    return { transfers: greedySettle(nonZero), optimal: false };
  }
  const groups = partitionIntoZeroSumGroups(nonZero);
  return { transfers: groups.flatMap(greedySettle), optimal: true };
}

/**
 * Partitions zero-sum items into the maximum number of disjoint zero-sum subgroups
 * (bitmask DP). Members keep ascending input order; groups are ordered by smallest index.
 */
export function partitionIntoZeroSumGroups(items: Balance[]): Balance[][] {
  const n = items.length;
  if (n === 0) {
    return [];
  }
  const size = 1 << n;
  const full = size - 1;
  const sum: bigint[] = new Array<bigint>(size);
  const dp = new Int32Array(size);
  const choice = new Int8Array(size);
  sum[0] = 0n;

  for (let mask = 1; mask <= full; mask++) {
    const low = 31 - Math.clz32(mask & -mask);
    sum[mask] = (sum[mask & (mask - 1)] as bigint) + (items[low] as Balance).net;

    let best = -1;
    let bestBit = -1;
    for (let i = 0; i < n; i++) {
      if ((mask & (1 << i)) !== 0) {
        const candidate = dp[mask ^ (1 << i)] as number;
        if (candidate > best) {
          best = candidate;
          bestBit = i;
        }
      }
    }
    dp[mask] = best + (sum[mask] === 0n ? 1 : 0);
    choice[mask] = bestBit;
  }

  const groups: number[][] = [];
  let bucket: number[] = [];
  let mask = full;
  while (mask !== 0) {
    const i = choice[mask] as number;
    bucket.push(i);
    mask ^= 1 << i;
    if (sum[mask] === 0n) {
      groups.push(bucket);
      bucket = [];
    }
  }
  if (bucket.length > 0) {
    // Only reachable when items do not sum to zero; keep them together.
    groups.push(bucket);
  }

  return groups
    .map((indices) => indices.sort((a, b) => a - b))
    .sort((a, b) => (a[0] as number) - (b[0] as number))
    .map((indices) => indices.map((i) => items[i] as Balance));
}

interface Party {
  memberId: string;
  remaining: bigint;
  order: number;
}

/**
 * Repeatedly settles the largest debtor against the largest creditor (ties → earliest input).
 * Each transfer zeroes at least one party, so at most items − 1 transfers are produced.
 */
export function greedySettle(items: Balance[]): Transfer[] {
  const creditors: Party[] = [];
  const debtors: Party[] = [];
  items.forEach((b, order) => {
    if (b.net > 0n) creditors.push({ memberId: b.memberId, remaining: b.net, order });
    else if (b.net < 0n) debtors.push({ memberId: b.memberId, remaining: -b.net, order });
  });

  const largest = (parties: Party[]): Party => {
    let best = parties[0] as Party;
    for (const p of parties) {
      if (p.remaining > best.remaining || (p.remaining === best.remaining && p.order < best.order)) {
        best = p;
      }
    }
    return best;
  };

  const transfers: Transfer[] = [];
  while (creditors.length > 0 && debtors.length > 0) {
    const creditor = largest(creditors);
    const debtor = largest(debtors);
    const amount = creditor.remaining < debtor.remaining ? creditor.remaining : debtor.remaining;
    transfers.push({ fromMemberId: debtor.memberId, toMemberId: creditor.memberId, amount });
    creditor.remaining -= amount;
    debtor.remaining -= amount;
    if (creditor.remaining === 0n) creditors.splice(creditors.indexOf(creditor), 1);
    if (debtor.remaining === 0n) debtors.splice(debtors.indexOf(debtor), 1);
  }
  return transfers;
}
