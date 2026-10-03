import type { Expense, Group, Member } from '../domain/types.js';

export interface GroupRepository {
  save(group: Group): void;
  findById(id: string): Group | undefined;
}

export interface MemberRepository {
  save(member: Member): void;
  /** Members of the group in insertion (seq) order. */
  findByGroup(groupId: string): Member[];
  countByGroup(groupId: string): number;
}

export interface ExpenseRepository {
  save(expense: Expense): void;
  /** Expenses of the group in insertion order. */
  findByGroup(groupId: string): Expense[];
}
