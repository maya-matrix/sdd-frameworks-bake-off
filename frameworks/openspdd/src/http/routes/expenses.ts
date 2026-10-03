import type { FastifyInstance } from 'fastify';
import type { RouteOptions } from '../../app.js';
import { toExpenseResponse } from '../mappers.js';
import {
  groupIdParams,
  recordExpenseBody,
  type GroupIdParams,
  type RecordExpenseBody,
} from '../schemas.js';

export async function expenseRoutes(app: FastifyInstance, { services }: RouteOptions) {
  app.post<{ Params: GroupIdParams; Body: RecordExpenseBody }>(
    '/groups/:groupId/expenses',
    { schema: { params: groupIdParams, body: recordExpenseBody } },
    async (request, reply) => {
      const expense = services.expenses.recordExpense(request.params.groupId, request.body);
      return reply.status(201).send(toExpenseResponse(expense));
    },
  );

  app.get<{ Params: GroupIdParams }>(
    '/groups/:groupId/expenses',
    { schema: { params: groupIdParams } },
    async (request) => ({
      expenses: services.expenses.listExpenses(request.params.groupId).map(toExpenseResponse),
    }),
  );
}
