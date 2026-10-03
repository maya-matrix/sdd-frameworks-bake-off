import type { FastifyInstance } from 'fastify';
import type { RouteOptions } from '../../app.js';
import { toMemberResponse } from '../mappers.js';
import { addMemberBody, groupIdParams, type GroupIdParams, type NameBody } from '../schemas.js';

export async function memberRoutes(app: FastifyInstance, { services }: RouteOptions) {
  app.post<{ Params: GroupIdParams; Body: NameBody }>(
    '/groups/:groupId/members',
    { schema: { params: groupIdParams, body: addMemberBody } },
    async (request, reply) => {
      const member = services.groups.addMember(request.params.groupId, request.body.name);
      return reply.status(201).send(toMemberResponse(member));
    },
  );

  app.get<{ Params: GroupIdParams }>(
    '/groups/:groupId/members',
    { schema: { params: groupIdParams } },
    async (request) => ({
      members: services.groups.listMembers(request.params.groupId).map(toMemberResponse),
    }),
  );
}
