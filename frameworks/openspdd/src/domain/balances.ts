import type { Balance, Expense, Member } from './types.js';

/**
 * Net balance per member = total paid − total owed. Every member appears (0n if inactive),
 * ordered by seq. Invariant: balances sum to exactly 0n.
 */
export function computeBalances(members: Member[], expenses: Expense[]): Balance[] {
  const net = new Map<string, bigint>();
  for (const member of members) {
    net.set(member.id, 0n);
  }
  const add = (memberId: string, delta: bigint): void => {
    net.set(memberId, (net.get(memberId) ?? 0n) + delta);
  };
  for (const expense of expenses) {
    add(expense.payerId, expense.amount);
    for (const share of expense.shares) {
      add(share.memberId, -share.amount);
    }
  }
  return [...members]
    .sort((a, b) => a.seq - b.seq)
    .map((member) => ({ memberId: member.id, net: net.get(member.id) ?? 0n }));
}
