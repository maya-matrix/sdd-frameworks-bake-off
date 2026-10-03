import type { Cents } from "./money.js";
import type { Share } from "./split.js";

export interface ExpenseEntry {
  payerId: string;
  amount: Cents;
  shares: readonly Share[];
}

export interface Balance {
  memberId: string;
  balance: Cents;
}

/**
 * Net balance per member: total paid minus total of their shares.
 * Positive means the member is owed money. Returned in member order and
 * includes members with no activity at zero. Sums to exactly zero because
 * each expense's shares sum to its amount.
 */
export function computeBalances(
  memberOrder: readonly string[],
  expenses: readonly ExpenseEntry[],
): Balance[] {
  const totals = new Map<string, Cents>(memberOrder.map((id) => [id, 0n]));
  const add = (id: string, delta: Cents) => totals.set(id, (totals.get(id) ?? 0n) + delta);
  for (const expense of expenses) {
    add(expense.payerId, expense.amount);
    for (const { memberId, share } of expense.shares) {
      add(memberId, -share);
    }
  }
  return memberOrder.map((memberId) => ({ memberId, balance: totals.get(memberId) ?? 0n }));
}
