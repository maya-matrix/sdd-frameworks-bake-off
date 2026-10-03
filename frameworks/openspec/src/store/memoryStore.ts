import { randomUUID } from "node:crypto";
import { ConflictError, NotFoundError, ValidationError } from "../domain/errors.js";
import { FULL_PERCENTAGE, type BasisPoints, type Cents } from "../domain/money.js";
import { splitByPercentage, splitEqually, splitExact, type Share } from "../domain/split.js";

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

export type SplitType = "equal" | "exact" | "percentage";

/** One participant of an unequal split: `amount` for "exact", `basisPoints` for "percentage". */
export interface SplitInput {
  memberId: string;
  amount?: Cents;
  basisPoints?: BasisPoints;
}

export interface Expense {
  id: string;
  groupId: string;
  payerId: string;
  amount: Cents;
  description: string;
  splitType: SplitType;
  /** Participant ids; for unequal splits, in the order they were listed in `splits`. */
  splitBetween: string[];
  /** The submitted per-member values; only present for "exact" and "percentage". */
  splits?: SplitInput[];
  shares: Share[];
  createdAt: string;
}

export interface NewExpense {
  payerId: string;
  amount: Cents;
  description: string;
  /** Defaults to "equal". */
  splitType?: SplitType;
  /** Participants of an "equal" split. */
  splitBetween?: string[];
  /** Participants of an "exact" or "percentage" split. */
  splits?: SplitInput[];
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
    const splitType = input.splitType ?? "equal";
    const split =
      splitType === "equal"
        ? equalSplit(input, memberIds, isMember)
        : unequalSplit(splitType, input, memberIds, isMember);

    const expense: Expense = {
      id: randomUUID(),
      groupId,
      payerId: input.payerId,
      amount: input.amount,
      description,
      splitType,
      ...split,
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

type ResolvedSplit = Pick<Expense, "splitBetween" | "splits" | "shares">;

function equalSplit(input: NewExpense, memberIds: string[], isMember: Set<string>): ResolvedSplit {
  if (input.splits !== undefined) {
    throw new ValidationError('splits is only allowed with splitType "exact" or "percentage"');
  }
  const splitBetween = input.splitBetween ?? [];
  if (splitBetween.length === 0) {
    throw new ValidationError("splitBetween must list at least one member");
  }
  if (new Set(splitBetween).size !== splitBetween.length) {
    throw new ValidationError("splitBetween must not contain duplicate members");
  }
  const outsider = splitBetween.find((id) => !isMember.has(id));
  if (outsider !== undefined) {
    throw new ValidationError(`Participant ${outsider} is not a member of this group`);
  }
  return {
    splitBetween: [...splitBetween],
    shares: splitEqually(input.amount, splitBetween, memberIds),
  };
}

function unequalSplit(
  splitType: "exact" | "percentage",
  input: NewExpense,
  memberIds: string[],
  isMember: Set<string>,
): ResolvedSplit {
  if (input.splitBetween !== undefined) {
    throw new ValidationError(`splitBetween is not allowed with splitType "${splitType}"; use splits`);
  }
  const splits = input.splits ?? [];
  if (splits.length === 0) {
    throw new ValidationError("splits must list at least one member");
  }
  const ids = splits.map((s) => s.memberId);
  if (new Set(ids).size !== ids.length) {
    throw new ValidationError("splits must not contain duplicate members");
  }
  const outsider = ids.find((id) => !isMember.has(id));
  if (outsider !== undefined) {
    throw new ValidationError(`Participant ${outsider} is not a member of this group`);
  }

  if (splitType === "exact") {
    const entries = splits.map(({ memberId, amount, basisPoints }) => {
      if (amount === undefined || basisPoints !== undefined) {
        throw new ValidationError("Each exact split must have an amount and no percentage");
      }
      if (amount < 0n) {
        throw new ValidationError("Split amounts must not be negative");
      }
      return { memberId, amount };
    });
    if (entries.reduce((sum, e) => sum + e.amount, 0n) !== input.amount) {
      throw new ValidationError("Split amounts must sum exactly to the expense amount");
    }
    return {
      splitBetween: ids,
      splits: entries.map((e) => ({ ...e })),
      shares: splitExact(entries, memberIds),
    };
  }

  const entries = splits.map(({ memberId, amount, basisPoints }) => {
    if (basisPoints === undefined || amount !== undefined) {
      throw new ValidationError("Each percentage split must have a percentage and no amount");
    }
    if (basisPoints < 0n || basisPoints > FULL_PERCENTAGE) {
      throw new ValidationError("Percentages must be between 0 and 100");
    }
    return { memberId, basisPoints };
  });
  if (entries.reduce((sum, e) => sum + e.basisPoints, 0n) !== FULL_PERCENTAGE) {
    throw new ValidationError("Percentages must sum exactly to 100");
  }
  return {
    splitBetween: ids,
    splits: entries.map((e) => ({ ...e })),
    shares: splitByPercentage(input.amount, entries, memberIds),
  };
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
    ...(expense.splits && { splits: expense.splits.map((s) => ({ ...s })) }),
    shares: expense.shares.map((s) => ({ ...s })),
  };
}
