import type { FastifyPluginAsync } from "fastify";
import { formatAmount, parseAmount } from "../../domain/money.js";
import type { Expense, Repository } from "../../store/memoryStore.js";

interface ExpenseBody {
  payerId: string;
  amount: string;
  description: string;
  splitBetween: string[];
}

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
            required: ["payerId", "amount", "description", "splitBetween"],
            properties: {
              payerId: { type: "string" },
              // A string, never a JSON number, so the value is exact on the wire.
              amount: { type: "string", pattern: "^\\d+(\\.\\d{1,2})?$" },
              description: { type: "string" },
              splitBetween: { type: "array", items: { type: "string" } },
            },
          },
        },
      },
      async (request, reply) => {
        const { payerId, amount, description, splitBetween } = request.body;
        const expense = store.recordExpense(request.params.groupId, {
          payerId,
          amount: parseAmount(amount),
          description,
          splitBetween,
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

function serializeExpense(expense: Expense) {
  return {
    id: expense.id,
    groupId: expense.groupId,
    payerId: expense.payerId,
    amount: formatAmount(expense.amount),
    description: expense.description,
    splitBetween: expense.splitBetween,
    shares: expense.shares.map((s) => ({ memberId: s.memberId, share: formatAmount(s.share) })),
    createdAt: expense.createdAt,
  };
}
