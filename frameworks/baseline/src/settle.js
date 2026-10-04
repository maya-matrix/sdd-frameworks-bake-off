// Settle-up: find the fewest transfers that bring every balance to zero.
//
// A group of k people whose balances sum to zero can always be settled with
// k - 1 transfers, and never fewer. So the minimum number of transfers for the
// whole set is (people with a non-zero balance) - (the largest number of
// disjoint zero-sum subgroups they can be partitioned into). Finding that
// partition is NP-hard in general, so we solve it exactly with a DP over
// subsets, which is fast for groups of up to EXACT_LIMIT open balances. Beyond
// that we fall back to a greedy heuristic and report `optimal: false`.

export const EXACT_LIMIT = 20;
const INT64_MAX = (1n << 63n) - 1n;

/**
 * @param {{ id: string, amount: bigint }[]} balances  positive = is owed money
 * @returns {{ transfers: { from: string, to: string, amount: bigint }[], optimal: boolean }}
 */
export function minimumTransfers(balances) {
  const open = balances.filter((b) => b.amount !== 0n);
  let total = 0n;
  let absTotal = 0n;
  for (const { amount } of open) {
    total += amount;
    absTotal += amount < 0n ? -amount : amount;
  }
  if (total !== 0n) throw new Error('balances must sum to zero');

  // Subset sums are stored in a BigInt64Array; they are bounded by absTotal.
  if (open.length <= EXACT_LIMIT && absTotal <= INT64_MAX) {
    const groups = maxZeroSumPartition(open.map((b) => b.amount));
    const transfers = groups.flatMap((indices) => settleGroup(indices.map((i) => open[i])));
    return { transfers, optimal: true };
  }
  return { transfers: settleGroup(open), optimal: false };
}

/**
 * Partition indices of `amounts` (which sum to zero) into the maximum number
 * of disjoint subsets that each sum to zero.
 */
function maxZeroSumPartition(amounts) {
  const n = amounts.length;
  const size = 1 << n;
  const sums = new BigInt64Array(size);
  // best[mask] = most zero-sum "prefixes" reachable when removing elements of mask one at a time.
  const best = new Uint8Array(size);

  for (let mask = 1; mask < size; mask++) {
    const low = mask & -mask;
    sums[mask] = sums[mask ^ low] + amounts[31 - Math.clz32(low)];
    let max = 0;
    for (let j = 0; j < n; j++) {
      if (mask & (1 << j) && best[mask ^ (1 << j)] > max) max = best[mask ^ (1 << j)];
    }
    best[mask] = max + (sums[mask] === 0n ? 1 : 0);
  }

  // Walk back down from the full set along an optimal path, cutting a group
  // off every time the remaining elements sum to zero.
  const groups = [];
  let current = [];
  let mask = size - 1;
  while (mask) {
    const target = best[mask] - (sums[mask] === 0n ? 1 : 0);
    let j = 0;
    while (!(mask & (1 << j)) || best[mask ^ (1 << j)] !== target) j++;
    current.push(j);
    mask ^= 1 << j;
    if (sums[mask] === 0n) {
      groups.push(current.sort((a, b) => a - b));
      current = [];
    }
  }
  return groups;
}

/**
 * Settle a zero-sum set of balances by repeatedly matching the largest debtor
 * with the largest creditor. Every transfer clears at least one person and the
 * last clears two, so k people need at most k - 1 transfers.
 */
function settleGroup(entries) {
  const byAmountDesc = (a, b) => (a.left > b.left ? -1 : a.left < b.left ? 1 : 0);
  const debtors = entries.filter((e) => e.amount < 0n).map((e) => ({ id: e.id, left: -e.amount })).sort(byAmountDesc);
  const creditors = entries.filter((e) => e.amount > 0n).map((e) => ({ id: e.id, left: e.amount })).sort(byAmountDesc);

  const transfers = [];
  let d = 0;
  let c = 0;
  while (d < debtors.length && c < creditors.length) {
    const amount = debtors[d].left < creditors[c].left ? debtors[d].left : creditors[c].left;
    transfers.push({ from: debtors[d].id, to: creditors[c].id, amount });
    debtors[d].left -= amount;
    creditors[c].left -= amount;
    if (debtors[d].left === 0n) d++;
    if (creditors[c].left === 0n) c++;
  }
  return transfers;
}
