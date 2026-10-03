import type { FastifyInstance } from 'fastify';
import type { RouteOptions } from '../../app.js';
import { toGroupResponse } from '../mappers.js';
import { createGroupBody, groupIdParams, type GroupIdParams, type NameBody } from '../schemas.js';

export async function groupRoutes(app: FastifyInstance, { services }: RouteOptions) {
  app.post<{ Body: NameBody }>('/groups', { schema: { body: createGroupBody } }, async (request, reply) => {
    const group = services.groups.createGroup(request.body.name);
    return reply.status(201).send(toGroupResponse(group, []));
  });

  app.get<{ Params: GroupIdParams }>(
    '/groups/:groupId',
    { schema: { params: groupIdParams } },
    async (request) => {
      const group = services.groups.getGroup(request.params.groupId);
      return toGroupResponse(group, services.groups.listMembers(group.id));
    },
  );
}
