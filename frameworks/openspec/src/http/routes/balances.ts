import type { FastifyPluginAsync } from "fastify";
import { computeBalances } from "../../domain/balances.js";
import { formatAmount } from "../../domain/money.js";
import { settleUp } from "../../domain/settle.js";
import type { Repository } from "../../store/memoryStore.js";

const groupParams = {
  type: "object",
  required: ["groupId"],
  properties: { groupId: { type: "string" } },
} as const;

export function balanceRoutes(store: Repository): FastifyPluginAsync {
  return async (app) => {
    const balancesOf = (groupId: string) => {
      const group = store.getGroup(groupId);
      const balances = computeBalances(
        group.members.map((m) => m.id),
        store.listExpenses(groupId),
      );
      return { group, balances };
    };

    app.get<{ Params: { groupId: string } }>(
      "/groups/:groupId/balances",
      { schema: { params: groupParams } },
      async (request) => {
        const { group, balances } = balancesOf(request.params.groupId);
        const names = new Map(group.members.map((m) => [m.id, m.name]));
        return {
          balances: balances.map((b) => ({
            memberId: b.memberId,
            name: names.get(b.memberId),
            balance: formatAmount(b.balance),
          })),
        };
      },
    );

    app.get<{ Params: { groupId: string } }>(
      "/groups/:groupId/settle-up",
      { schema: { params: groupParams } },
      async (request) => {
        const plan = settleUp(balancesOf(request.params.groupId).balances);
        return {
          transfers: plan.transfers.map((t) => ({
            from: t.from,
            to: t.to,
            amount: formatAmount(t.amount),
          })),
          optimal: plan.optimal,
        };
      },
    );
  };
}
