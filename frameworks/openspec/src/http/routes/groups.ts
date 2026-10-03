import type { FastifyPluginAsync } from "fastify";
import type { Repository } from "../../store/memoryStore.js";

const nonBlank = { type: "string", pattern: "\\S" } as const;

const groupParams = {
  type: "object",
  required: ["groupId"],
  properties: { groupId: { type: "string" } },
} as const;

export function groupRoutes(store: Repository): FastifyPluginAsync {
  return async (app) => {
    app.post<{ Body: { name: string; members?: string[] } }>(
      "/groups",
      {
        schema: {
          body: {
            type: "object",
            required: ["name"],
            properties: {
              name: nonBlank,
              members: { type: "array", items: nonBlank },
            },
          },
        },
      },
      async (request, reply) => {
        const group = store.createGroup(request.body.name, request.body.members ?? []);
        return reply.status(201).send(group);
      },
    );

    app.get<{ Params: { groupId: string } }>(
      "/groups/:groupId",
      { schema: { params: groupParams } },
      async (request) => store.getGroup(request.params.groupId),
    );

    app.post<{ Params: { groupId: string }; Body: { name: string } }>(
      "/groups/:groupId/members",
      {
        schema: {
          params: groupParams,
          body: { type: "object", required: ["name"], properties: { name: nonBlank } },
        },
      },
      async (request, reply) => {
        const member = store.addMember(request.params.groupId, request.body.name);
        return reply.status(201).send(member);
      },
    );
  };
}
