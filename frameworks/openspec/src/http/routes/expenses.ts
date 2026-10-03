import type { FastifyPluginAsync } from "fastify";
import { ValidationError } from "../../domain/errors.js";
import { formatAmount, formatPercentage, InvalidAmountError, parseAmount, parsePercentage } from "../../domain/money.js";
import type { Expense, Repository, SplitInput, SplitType } from "../../store/memoryStore.js";

interface SplitBody {
  memberId: string;
  amount?: string;
  percentage?: string;
}

interface ExpenseBody {
  payerId: string;
  amount: string;
  description: string;
  splitType?: SplitType;
  splitBetween?: string[];
  splits?: SplitBody[];
}

// A string, never a JSON number, so the value is exact on the wire.
const decimalString = { type: "string", pattern: "^\\d+(\\.\\d{1,2})?$" } as const;

const groupParams = {
  type: "object",
  required: ["groupId"],
  properties: { groupId: { type: "string" } },
} as const;

export function expenseRoutes(store: Repository): FastifyPluginAsync {
  return async (app) => {
    app.post<{ Params: { groupId: string }; Body: ExpenseBody }>(
      "/groups/:groupId/expenses",
      {
        schema: {
          params: groupParams,
          body: {
            type: "object",
            // Which of splitBetween / splits goes with which splitType is checked by the store.
            required: ["payerId", "amount", "description"],
            properties: {
              payerId: { type: "string" },
              amount: decimalString,
              description: { type: "string" },
              splitType: { type: "string", enum: ["equal", "exact", "percentage"] },
              splitBetween: { type: "array", items: { type: "string" } },
              splits: {
                type: "array",
                items: {
                  type: "object",
                  required: ["memberId"],
                  properties: {
                    memberId: { type: "string" },
                    amount: decimalString,
                    percentage: decimalString,
                  },
                },
              },
            },
          },
        },
      },
      async (request, reply) => {
        const { payerId, amount, description, splitType, splitBetween, splits } = request.body;
        const expense = store.recordExpense(request.params.groupId, {
          payerId,
          amount: parseAmount(amount),
          description,
          splitType,
          splitBetween,
          splits: splits?.map(parseSplit),
        });
        return reply.status(201).send(serializeExpense(expense));
      },
    );

    app.get<{ Params: { groupId: string } }>(
      "/groups/:groupId/expenses",
      { schema: { params: groupParams } },
      async (request) => ({
        expenses: store.listExpenses(request.params.groupId).map(serializeExpense),
      }),
    );
  };
}

function parseSplit({ memberId, amount, percentage }: SplitBody): SplitInput {
  try {
    return {
      memberId,
      ...(amount !== undefined && { amount: parseAmount(amount) }),
      ...(percentage !== undefined && { basisPoints: parsePercentage(percentage) }),
    };
  } catch (error) {
    if (error instanceof InvalidAmountError) {
      throw new ValidationError("Percentages must be between 0 and 100 with at most two fraction digits");
    }
    throw error;
  }
}

function serializeExpense(expense: Expense) {
  return {
    id: expense.id,
    groupId: expense.groupId,
    payerId: expense.payerId,
    amount: formatAmount(expense.amount),
    description: expense.description,
    splitType: expense.splitType,
    splitBetween: expense.splitBetween,
    ...(expense.splits && {
      splits: expense.splits.map((s) => ({
        memberId: s.memberId,
        ...(s.amount !== undefined && { amount: formatAmount(s.amount) }),
        ...(s.basisPoints !== undefined && { percentage: formatPercentage(s.basisPoints) }),
      })),
    }),
    shares: expense.shares.map((s) => ({ memberId: s.memberId, share: formatAmount(s.share) })),
    createdAt: expense.createdAt,
  };
}
