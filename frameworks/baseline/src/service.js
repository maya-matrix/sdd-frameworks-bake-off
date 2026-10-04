// Domain logic for users, groups and expenses, kept independent of HTTP.
// State is held in memory.

import { randomUUID } from 'node:crypto';
import { MoneyError, formatCents, parseAmount, splitEqually } from './money.js';
import { minimumTransfers } from './settle.js';

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const badRequest = (message) => new ApiError(400, 'validation_error', message);

function requireText(value, field, maxLength) {
  if (typeof value !== 'string' || value.trim() === '') throw badRequest(`${field} must be a non-empty string`);
  const text = value.trim();
  if (text.length > maxLength) throw badRequest(`${field} must be at most ${maxLength} characters`);
  return text;
}

function requireId(value, field) {
  if (typeof value !== 'string' || value === '') throw badRequest(`${field} must be a user id string`);
  return value;
}

export class ExpenseService {
  #users = new Map();
  #groups = new Map();

  createUser({ name } = {}) {
    const user = { id: randomUUID(), name: requireText(name, 'name', 100) };
    this.#users.set(user.id, user);
    return { ...user };
  }

  getUser(id) {
    const user = this.#users.get(id);
    if (!user) throw new ApiError(404, 'not_found', 'user not found');
    return { ...user };
  }

  /** Resolve the caller; any request acting on behalf of a user goes through here. */
  authenticate(actorId) {
    if (!actorId) throw new ApiError(401, 'unauthenticated', 'X-User-Id header is required');
    const user = this.#users.get(actorId);
    if (!user) throw new ApiError(401, 'unauthenticated', 'X-User-Id does not match a known user');
    return user;
  }

  createGroup(actorId, { name } = {}) {
    const actor = this.authenticate(actorId);
    const group = {
      id: randomUUID(),
      name: requireText(name, 'name', 100),
      createdBy: actor.id,
      members: [actor.id],
      expenses: [],
    };
    this.#groups.set(group.id, group);
    return this.#serializeGroup(group);
  }

  getGroup(actorId, groupId) {
    return this.#serializeGroup(this.#groupForMember(actorId, groupId));
  }

  addMember(actorId, groupId, { userId } = {}) {
    const group = this.#groupForMember(actorId, groupId);
    requireId(userId, 'userId');
    if (!this.#users.has(userId)) throw new ApiError(404, 'not_found', 'user to add not found');
    if (group.members.includes(userId)) throw new ApiError(409, 'conflict', 'user is already a member of this group');
    group.members.push(userId);
    return this.#serializeGroup(group);
  }

  addExpense(actorId, groupId, { paidBy, amount, description, splitBetween } = {}) {
    const group = this.#groupForMember(actorId, groupId);
    const isMember = (id) => group.members.includes(id);

    requireId(paidBy, 'paidBy');
    if (!isMember(paidBy)) throw badRequest('paidBy must be a member of the group');

    let amountCents;
    try {
      amountCents = parseAmount(amount);
    } catch (err) {
      if (err instanceof MoneyError) throw badRequest(err.message);
      throw err;
    }

    const text = requireText(description, 'description', 500);

    if (!Array.isArray(splitBetween) || splitBetween.length === 0) {
      throw badRequest('splitBetween must be a non-empty array of member ids');
    }
    splitBetween.forEach((id, i) => requireId(id, `splitBetween[${i}]`));
    if (new Set(splitBetween).size !== splitBetween.length) throw badRequest('splitBetween must not contain duplicates');
    const outsiders = splitBetween.filter((id) => !isMember(id));
    if (outsiders.length) throw badRequest(`splitBetween contains non-members: ${outsiders.join(', ')}`);

    const shareAmounts = splitEqually(amountCents, splitBetween.length);
    const expense = {
      id: randomUUID(),
      description: text,
      amount: amountCents,
      paidBy,
      shares: splitBetween.map((userId, i) => ({ userId, amount: shareAmounts[i] })),
      createdBy: actorId,
      createdAt: new Date().toISOString(),
    };
    group.expenses.push(expense);
    return serializeExpense(expense);
  }

  listExpenses(actorId, groupId) {
    return this.#groupForMember(actorId, groupId).expenses.map(serializeExpense);
  }

  getBalances(actorId, groupId) {
    const group = this.#groupForMember(actorId, groupId);
    return {
      groupId: group.id,
      balances: this.#netBalances(group).map(({ id, amount }) => ({
        userId: id,
        name: this.#users.get(id).name,
        balance: formatCents(amount),
      })),
    };
  }

  settleUp(actorId, groupId) {
    const group = this.#groupForMember(actorId, groupId);
    const { transfers, optimal } = minimumTransfers(this.#netBalances(group));
    const name = (id) => this.#users.get(id).name;
    return {
      groupId: group.id,
      optimal,
      transfers: transfers.map((t) => ({
        from: t.from,
        fromName: name(t.from),
        to: t.to,
        toName: name(t.to),
        amount: formatCents(t.amount),
      })),
    };
  }

  /** Net balance per member in cents: positive means the group owes them. */
  #netBalances(group) {
    const net = new Map(group.members.map((id) => [id, 0n]));
    for (const expense of group.expenses) {
      net.set(expense.paidBy, net.get(expense.paidBy) + expense.amount);
      for (const share of expense.shares) net.set(share.userId, net.get(share.userId) - share.amount);
    }
    return [...net].map(([id, amount]) => ({ id, amount }));
  }

  #groupForMember(actorId, groupId) {
    const actor = this.authenticate(actorId);
    const group = this.#groups.get(groupId);
    if (!group) throw new ApiError(404, 'not_found', 'group not found');
    if (!group.members.includes(actor.id)) throw new ApiError(403, 'forbidden', 'you are not a member of this group');
    return group;
  }

  #serializeGroup(group) {
    return {
      id: group.id,
      name: group.name,
      createdBy: group.createdBy,
      members: group.members.map((id) => ({ ...this.#users.get(id) })),
    };
  }
}

function serializeExpense(expense) {
  return {
    id: expense.id,
    description: expense.description,
    amount: formatCents(expense.amount),
    paidBy: expense.paidBy,
    splitBetween: expense.shares.map((s) => ({ userId: s.userId, amount: formatCents(s.amount) })),
    createdBy: expense.createdBy,
    createdAt: expense.createdAt,
  };
}
