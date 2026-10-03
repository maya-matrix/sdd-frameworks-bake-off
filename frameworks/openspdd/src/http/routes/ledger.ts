import type { FastifyInstance } from 'fastify';
import type { RouteOptions } from '../../app.js';
import { toBalancesResponse, toSettleUpResponse } from '../mappers.js';
import { groupIdParams, type GroupIdParams } from '../schemas.js';

export async function ledgerRoutes(app: FastifyInstance, { services }: RouteOptions) {
  app.get<{ Params: GroupIdParams }>(
    '/groups/:groupId/balances',
    { schema: { params: groupIdParams } },
    async (request) => toBalancesResponse(services.settlements.getBalances(request.params.groupId)),
  );

  app.get<{ Params: GroupIdParams }>(
    '/groups/:groupId/settle-up',
    { schema: { params: groupIdParams } },
    async (request) => {
      const { groupId } = request.params;
      const plan = services.settlements.getSettlement(groupId);
      const membersById = new Map(services.groups.listMembers(groupId).map((m) => [m.id, m]));
      return toSettleUpResponse(plan, membersById);
    },
  );
}
