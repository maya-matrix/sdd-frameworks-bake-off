/** Base class for all expected failures; each subclass maps one-to-one to an HTTP status. */
export abstract class AppError extends Error {
  abstract readonly statusCode: number;
  abstract readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = new.target.name;
    if (details !== undefined) {
      this.details = details;
    }
  }
}

/** Input passed the schema but failed domain-level format checks (e.g. amount format). */
export class ValidationError extends AppError {
  readonly statusCode = 400;
  readonly code = 'VALIDATION_ERROR';
}

export type NotFoundCode = 'GROUP_NOT_FOUND';

/** A resource addressed by the request path does not exist. */
export class NotFoundError extends AppError {
  readonly statusCode = 404;
  readonly code: NotFoundCode;

  constructor(code: NotFoundCode, message: string, details?: Record<string, unknown>) {
    super(message, details);
    this.code = code;
  }
}

/** The request conflicts with existing state (uniqueness). */
export class ConflictError extends AppError {
  readonly statusCode = 409;
  readonly code = 'DUPLICATE_MEMBER_NAME';
}

export type BusinessRuleCode = 'UNKNOWN_MEMBER' | 'DUPLICATE_PARTICIPANT' | 'INVALID_AMOUNT';

/** The request is well-formed but violates an expense business rule. */
export class BusinessRuleError extends AppError {
  readonly statusCode = 422;
  readonly code: BusinessRuleCode;

  constructor(code: BusinessRuleCode, message: string, details?: Record<string, unknown>) {
    super(message, details);
    this.code = code;
  }
}
