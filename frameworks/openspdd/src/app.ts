import Fastify, { type FastifyInstance } from 'fastify';
import { errorHandler, notFoundHandler } from './http/error-handler.js';
import { expenseRoutes } from './http/routes/expenses.js';
import { groupRoutes } from './http/routes/groups.js';
import { ledgerRoutes } from './http/routes/ledger.js';
import { memberRoutes } from './http/routes/members.js';
import {
  InMemoryExpenseRepository,
  InMemoryGroupRepository,
  InMemoryMemberRepository,
} from './repositories/in-memory.js';
import { ExpenseService } from './services/expense-service.js';
import { GroupService } from './services/group-service.js';
import { SettlementService } from './services/settlement-service.js';

export interface Services {
  groups: GroupService;
  expenses: ExpenseService;
  settlements: SettlementService;
}

export interface RouteOptions {
  services: Services;
}

/** Composition root: a fresh app with fresh in-memory state on every call. */
export function buildApp(options?: { logger?: boolean }): FastifyInstance {
  const app = Fastify({
    logger: options?.logger ?? false,
    ajv: { customOptions: { coerceTypes: false, removeAdditional: false, allErrors: false } },
  });

  const expenseRepository = new InMemoryExpenseRepository();
  const groups = new GroupService(new InMemoryGroupRepository(), new InMemoryMemberRepository());
  const services: Services = {
    groups,
    expenses: new ExpenseService(groups, expenseRepository),
    settlements: new SettlementService(groups, expenseRepository),
  };

  app.setErrorHandler(errorHandler);
  app.setNotFoundHandler(notFoundHandler);

  app.register(groupRoutes, { services });
  app.register(memberRoutes, { services });
  app.register(expenseRoutes, { services });
  app.register(ledgerRoutes, { services });

  return app;
}
