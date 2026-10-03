import type { Expense, Group, Member } from '../domain/types.js';
import type { ExpenseRepository, GroupRepository, MemberRepository } from './types.js';

export class InMemoryGroupRepository implements GroupRepository {
  private readonly groups = new Map<string, Group>();

  save(group: Group): void {
    this.groups.set(group.id, { ...group });
  }

  findById(id: string): Group | undefined {
    const group = this.groups.get(id);
    return group === undefined ? undefined : { ...group };
  }
}

export class InMemoryMemberRepository implements MemberRepository {
  private readonly membersByGroup = new Map<string, Member[]>();

  save(member: Member): void {
    const list = this.membersByGroup.get(member.groupId) ?? [];
    list.push({ ...member });
    this.membersByGroup.set(member.groupId, list);
  }

  findByGroup(groupId: string): Member[] {
    return (this.membersByGroup.get(groupId) ?? []).map((m) => ({ ...m }));
  }

  countByGroup(groupId: string): number {
    return this.membersByGroup.get(groupId)?.length ?? 0;
  }
}

export class InMemoryExpenseRepository implements ExpenseRepository {
  private readonly expensesByGroup = new Map<string, Expense[]>();

  save(expense: Expense): void {
    const list = this.expensesByGroup.get(expense.groupId) ?? [];
    list.push(structuredClone(expense));
    this.expensesByGroup.set(expense.groupId, list);
  }

  findByGroup(groupId: string): Expense[] {
    return (this.expensesByGroup.get(groupId) ?? []).map((e) => structuredClone(e));
  }
}
