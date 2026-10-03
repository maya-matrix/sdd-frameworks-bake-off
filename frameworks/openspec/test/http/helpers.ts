import type { FastifyInstance } from "fastify";
import { buildApp } from "../../src/http/app.js";

export interface TestGroup {
  id: string;
  ids: Record<string, string>;
}

export function newApp(): FastifyInstance {
  return buildApp();
}

export async function createGroup(app: FastifyInstance, members: string[], name = "Trip"): Promise<TestGroup> {
  const response = await app.inject({ method: "POST", url: "/groups", payload: { name, members } });
  if (response.statusCode !== 201) {
    throw new Error(`createGroup failed: ${response.body}`);
  }
  const group = response.json() as { id: string; members: { id: string; name: string }[] };
  return { id: group.id, ids: Object.fromEntries(group.members.map((m) => [m.name, m.id])) };
}

export function postExpense(app: FastifyInstance, groupId: string, payload: unknown) {
  return app.inject({ method: "POST", url: `/groups/${groupId}/expenses`, payload: payload as object });
}

export async function recordExpense(
  app: FastifyInstance,
  group: TestGroup,
  payer: string,
  amount: string,
  participants: string[],
  description = "Expense",
) {
  const response = await postExpense(app, group.id, {
    payerId: group.ids[payer],
    amount,
    description,
    splitBetween: participants.map((p) => group.ids[p]),
  });
  if (response.statusCode !== 201) {
    throw new Error(`recordExpense failed: ${response.body}`);
  }
  return response.json();
}

/** Balances keyed by member name. */
export async function balancesByName(app: FastifyInstance, groupId: string): Promise<Record<string, string>> {
  const response = await app.inject({ method: "GET", url: `/groups/${groupId}/balances` });
  const body = response.json() as { balances: { name: string; balance: string }[] };
  return Object.fromEntries(body.balances.map((b) => [b.name, b.balance]));
}
