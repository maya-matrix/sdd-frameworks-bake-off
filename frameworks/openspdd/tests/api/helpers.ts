import type { FastifyInstance } from 'fastify';

export async function createGroup(app: FastifyInstance, name = 'Trip'): Promise<string> {
  const res = await app.inject({ method: 'POST', url: '/groups', payload: { name } });
  return res.json().id as string;
}

export async function addMember(app: FastifyInstance, groupId: string, name: string): Promise<string> {
  const res = await app.inject({
    method: 'POST',
    url: `/groups/${groupId}/members`,
    payload: { name },
  });
  return res.json().id as string;
}

export function recordExpense(
  app: FastifyInstance,
  groupId: string,
  payload: Record<string, unknown>,
) {
  return app.inject({ method: 'POST', url: `/groups/${groupId}/expenses`, payload });
}

/** Parses a wire money string into cents without floating point. */
export function toCents(text: string): bigint {
  const negative = text.startsWith('-');
  const [units = '0', fraction = '00'] = text.replace('-', '').split('.');
  const cents = BigInt(units) * 100n + BigInt(fraction);
  return negative ? -cents : cents;
}
