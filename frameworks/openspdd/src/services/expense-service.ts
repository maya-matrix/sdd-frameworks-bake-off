import { randomUUID } from 'node:crypto';
import { MAX_AMOUNT_CENTS, parseMoney, splitEqually } from '../domain/money.js';
import type { Expense, Share } from '../domain/types.js';
import { BusinessRuleError } from '../errors.js';
import type { ExpenseRepository } from '../repositories/types.js';
import type { GroupService } from './group-service.js';

export interface RecordExpenseInput {
  payerId: string;
  amount: string;
  description: string;
  participantIds: string[];
}

export class ExpenseService {
  constructor(
    private readonly groupService: GroupService,
    private readonly expenses: ExpenseRepository,
  ) {}

  recordExpense(groupId: string, input: RecordExpenseInput): Expense {
    this.groupService.getGroup(groupId);

    const amount = parseMoney(input.amount);
    if (amount === 0n || amount > MAX_AMOUNT_CENTS) {
      throw new BusinessRuleError(
        'INVALID_AMOUNT',
        'amount must be greater than 0.00 and at most 9999999999.99',
      );
    }

    const memberIds = new Set(this.groupService.listMembers(groupId).map((m) => m.id));
    if (!memberIds.has(input.payerId)) {
      throw new BusinessRuleError('UNKNOWN_MEMBER', 'Payer is not a member of this group', {
        memberId: input.payerId,
      });
    }

    const seen = new Set<string>();
    for (const id of input.participantIds) {
      if (seen.has(id)) {
        throw new BusinessRuleError('DUPLICATE_PARTICIPANT', 'Participant is listed more than once', {
          memberId: id,
        });
      }
      seen.add(id);
    }

    for (const id of input.participantIds) {
      if (!memberIds.has(id)) {
        throw new BusinessRuleError('UNKNOWN_MEMBER', 'Participant is not a member of this group', {
          memberId: id,
        });
      }
    }

    const amounts = splitEqually(amount, input.participantIds.length);
    const shares: Share[] = input.participantIds.map((memberId, i) => ({
      memberId,
      amount: amounts[i] as bigint,
    }));

    const expense: Expense = {
      id: randomUUID(),
      groupId,
      payerId: input.payerId,
      amount,
      description: input.description.trim(),
      shares,
      createdAt: new Date().toISOString(),
    };
    this.expenses.save(expense);
    return expense;
  }

  listExpenses(groupId: string): Expense[] {
    this.groupService.getGroup(groupId);
    return this.expenses.findByGroup(groupId);
  }
}
