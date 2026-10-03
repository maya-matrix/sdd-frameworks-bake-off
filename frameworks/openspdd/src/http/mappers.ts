import { formatMoney } from '../domain/money.js';
import type { Expense, Group, Member, SettlementPlan } from '../domain/types.js';
import type { NamedBalance } from '../services/settlement-service.js';

// Mappers are the only place bigint money becomes a string; no bigint reaches JSON.stringify.

export function toMemberResponse(member: Member) {
  return { id: member.id, name: member.name };
}

export function toGroupResponse(group: Group, members: Member[]) {
  return {
    id: group.id,
    name: group.name,
    createdAt: group.createdAt,
    members: members.map(toMemberResponse),
  };
}

export function toExpenseResponse(expense: Expense) {
  return {
    id: expense.id,
    payerId: expense.payerId,
    amount: formatMoney(expense.amount),
    description: expense.description,
    shares: expense.shares.map((s) => ({ memberId: s.memberId, amount: formatMoney(s.amount) })),
    createdAt: expense.createdAt,
  };
}

export function toBalancesResponse(balances: NamedBalance[]) {
  return {
    balances: balances.map((b) => ({ memberId: b.memberId, name: b.name, net: formatMoney(b.net) })),
  };
}

export function toSettleUpResponse(plan: SettlementPlan, membersById: Map<string, Member>) {
  const ref = (id: string) => ({ id, name: membersById.get(id)?.name ?? '' });
  return {
    transfers: plan.transfers.map((t) => ({
      from: ref(t.fromMemberId),
      to: ref(t.toMemberId),
      amount: formatMoney(t.amount),
    })),
    optimal: plan.optimal,
  };
}
