import type { FastifyError, FastifyReply, FastifyRequest } from 'fastify';
import { AppError } from '../errors.js';

interface ErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

function body(code: string, message: string, details?: Record<string, unknown>): ErrorBody {
  return { error: details === undefined ? { code, message } : { code, message, details } };
}

/** Single global error handler: the only place errors become HTTP responses. */
export function errorHandler(error: FastifyError | Error, request: FastifyRequest, reply: FastifyReply) {
  if (error instanceof AppError) {
    return reply.status(error.statusCode).send(body(error.code, error.message, error.details));
  }

  const fastifyError = error as FastifyError;
  if (fastifyError.validation !== undefined) {
    return reply.status(400).send(body('VALIDATION_ERROR', fastifyError.message));
  }

  if (typeof fastifyError.code === 'string' && fastifyError.code.startsWith('FST_ERR_CTP_')) {
    const status = fastifyError.statusCode ?? 400;
    const code = status === 415 ? 'UNSUPPORTED_MEDIA_TYPE' : 'VALIDATION_ERROR';
    return reply.status(status).send(body(code, fastifyError.message));
  }

  request.log.error(error);
  return reply.status(500).send(body('INTERNAL_ERROR', 'Internal server error'));
}

export function notFoundHandler(_request: FastifyRequest, reply: FastifyReply) {
  return reply.status(404).send(body('ROUTE_NOT_FOUND', 'Route not found'));
}
