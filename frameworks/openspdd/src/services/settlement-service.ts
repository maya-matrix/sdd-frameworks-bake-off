import { computeBalances } from '../domain/balances.js';
import { suggestTransfers } from '../domain/settlement.js';
import type { Balance, SettlementPlan } from '../domain/types.js';
import type { ExpenseRepository } from '../repositories/types.js';
import type { GroupService } from './group-service.js';

export type NamedBalance = Balance & { name: string };

export class SettlementService {
  constructor(
    private readonly groupService: GroupService,
    private readonly expenses: ExpenseRepository,
  ) {}

  getBalances(groupId: string): NamedBalance[] {
    const members = this.groupService.listMembers(groupId);
    const names = new Map(members.map((m) => [m.id, m.name]));
    return computeBalances(members, this.expenses.findByGroup(groupId)).map((b) => ({
      ...b,
      name: names.get(b.memberId) ?? '',
    }));
  }

  getSettlement(groupId: string): SettlementPlan {
    const members = this.groupService.listMembers(groupId);
    return suggestTransfers(computeBalances(members, this.expenses.findByGroup(groupId)));
  }
}
