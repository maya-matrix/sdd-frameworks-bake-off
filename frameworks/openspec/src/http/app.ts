import Fastify, { type FastifyError, type FastifyInstance } from "fastify";
import { ConflictError, NotFoundError, ValidationError } from "../domain/errors.js";
import { MemoryStore, type Repository } from "../store/memoryStore.js";
import { balanceRoutes } from "./routes/balances.js";
import { expenseRoutes } from "./routes/expenses.js";
import { groupRoutes } from "./routes/groups.js";

export interface AppOptions {
  logger?: boolean;
}

export function buildApp(store: Repository = new MemoryStore(), options: AppOptions = {}): FastifyInstance {
  const app = Fastify({
    logger: options.logger ?? false,
    // Never coerce types: an amount sent as a JSON number must be rejected, not stringified.
    ajv: { customOptions: { coerceTypes: false, allErrors: false } },
  });

  app.setErrorHandler((error: FastifyError, request, reply) => {
    if (error instanceof NotFoundError) {
      return reply.status(404).send(errorBody(error.code, error.message));
    }
    if (error instanceof ConflictError) {
      return reply.status(409).send(errorBody(error.code, error.message));
    }
    if (error instanceof ValidationError) {
      return reply.status(400).send(errorBody(error.code, error.message));
    }
    if (error.validation || (error.statusCode !== undefined && error.statusCode >= 400 && error.statusCode < 500)) {
      // Schema validation failures and body parsing errors (malformed JSON, wrong content type, …).
      return reply.status(error.statusCode ?? 400).send(errorBody("VALIDATION_ERROR", error.message));
    }
    request.log.error(error);
    return reply.status(500).send(errorBody("INTERNAL", "Internal server error"));
  });

  app.setNotFoundHandler((request, reply) => {
    reply.status(404).send(errorBody("NOT_FOUND", `Route ${request.method} ${request.url} not found`));
  });

  app.register(groupRoutes(store));
  app.register(expenseRoutes(store));
  app.register(balanceRoutes(store));
  return app;
}

function errorBody(code: string, message: string) {
  return { error: { code, message } };
}
