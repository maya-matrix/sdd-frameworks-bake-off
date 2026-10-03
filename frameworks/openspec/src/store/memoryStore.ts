import { randomUUID } from "node:crypto";
import { ConflictError, NotFoundError, ValidationError } from "../domain/errors.js";
import type { Cents } from "../domain/money.js";
import { splitEqually, type Share } from "../domain/split.js";

export const MAX_EXPENSE_CENTS: Cents = 100_000_000_000n; // 1,000,000,000.00

export interface Member {
  id: string;
  name: string;
}

export interface Group {
  id: string;
  name: string;
  /** Members in the order they were added; this order drives remainder allocation. */
  members: Member[];
}

export interface Expense {
  id: string;
  groupId: string;
  payerId: string;
  amount: Cents;
  description: string;
  splitBetween: string[];
  shares: Share[];
  createdAt: string;
}

export interface NewExpense {
  payerId: string;
  amount: Cents;
  description: string;
  splitBetween: string[];
}

export interface Repository {
  createGroup(name: string, memberNames?: readonly string[]): Group;
  getGroup(groupId: string): Group;
  addMember(groupId: string, name: string): Member;
  recordExpense(groupId: string, input: NewExpense): Expense;
  listExpenses(groupId: string): Expense[];
}

interface GroupRecord {
  group: Group;
  expenses: Expense[];
}

const nameKey = (name: string) => name.trim().toLowerCase();

export class MemoryStore implements Repository {
  private readonly groups = new Map<string, GroupRecord>();

  createGroup(name: string, memberNames: readonly string[] = []): Group {
    const groupName = requireText(name, "Group name");
    const names = memberNames.map((n) => requireText(n, "Member name"));
    const seen = new Set<string>();
    for (const n of names) {
      if (seen.has(nameKey(n))) {
        throw new ConflictError(`Duplicate member name: ${n}`);
      }
      seen.add(nameKey(n));
    }
    const group: Group = {
      id: randomUUID(),
      name: groupName,
      members: names.map((n) => ({ id: randomUUID(), name: n })),
    };
    this.groups.set(group.id, { group, expenses: [] });
    return cloneGroup(group);
  }

  getGroup(groupId: string): Group {
    return cloneGroup(this.record(groupId).group);
  }

  addMember(groupId: string, name: string): Member {
    const { group } = this.record(groupId);
    const memberName = requireText(name, "Member name");
    if (group.members.some((m) => nameKey(m.name) === nameKey(memberName))) {
      throw new ConflictError(`A member named "${memberName}" already exists in this group`);
    }
    const member = { id: randomUUID(), name: memberName };
    group.members.push(member);
    return { ...member };
  }

  recordExpense(groupId: string, input: NewExpense): Expense {
    const record = this.record(groupId);
    const memberIds = record.group.members.map((m) => m.id);
    const isMember = new Set(memberIds);

    // Validate everything before mutating so a rejected request records nothing.
    if (input.amount <= 0n) {
      throw new ValidationError("Amount must be greater than zero");
    }
    if (input.amount > MAX_EXPENSE_CENTS) {
      throw new ValidationError("Amount must not exceed 1000000000.00");
    }
    const description = requireText(input.description, "Description");
    if (!isMember.has(input.payerId)) {
      throw new ValidationError("Payer is not a member of this group");
    }
    if (input.splitBetween.length === 0) {
      throw new ValidationError("splitBetween must list at least one member");
    }
    if (new Set(input.splitBetween).size !== input.splitBetween.length) {
      throw new ValidationError("splitBetween must not contain duplicate members");
    }
    const outsider = input.splitBetween.find((id) => !isMember.has(id));
    if (outsider !== undefined) {
      throw new ValidationError(`Participant ${outsider} is not a member of this group`);
    }

    const expense: Expense = {
      id: randomUUID(),
      groupId,
      payerId: input.payerId,
      amount: input.amount,
      description,
      splitBetween: [...input.splitBetween],
      shares: splitEqually(input.amount, input.splitBetween, memberIds),
      createdAt: new Date().toISOString(),
    };
    record.expenses.push(expense);
    return cloneExpense(expense);
  }

  listExpenses(groupId: string): Expense[] {
    return this.record(groupId).expenses.map(cloneExpense);
  }

  private record(groupId: string): GroupRecord {
    const record = this.groups.get(groupId);
    if (!record) {
      throw new NotFoundError(`Group ${groupId} not found`);
    }
    return record;
  }
}

function requireText(value: string, label: string): string {
  const trimmed = typeof value === "string" ? value.trim() : "";
  if (trimmed === "") {
    throw new ValidationError(`${label} must not be blank`);
  }
  return trimmed;
}

function cloneGroup(group: Group): Group {
  return { ...group, members: group.members.map((m) => ({ ...m })) };
}

function cloneExpense(expense: Expense): Expense {
  return {
    ...expense,
    splitBetween: [...expense.splitBetween],
    shares: expense.shares.map((s) => ({ ...s })),
  };
}
