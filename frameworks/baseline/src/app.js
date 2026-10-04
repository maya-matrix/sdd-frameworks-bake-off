// HTTP layer: routing, JSON parsing and error mapping around ExpenseService.

import { createServer } from 'node:http';
import { ApiError, ExpenseService } from './service.js';

const MAX_BODY_BYTES = 64 * 1024;

const routes = [
  ['POST', /^\/users$/, (s, ctx) => [201, s.createUser(ctx.body)]],
  ['GET', /^\/users\/([^/]+)$/, (s, ctx, [id]) => [200, s.getUser(id)]],
  ['POST', /^\/groups$/, (s, ctx) => [201, s.createGroup(ctx.actor, ctx.body)]],
  ['GET', /^\/groups\/([^/]+)$/, (s, ctx, [id]) => [200, s.getGroup(ctx.actor, id)]],
  ['POST', /^\/groups\/([^/]+)\/members$/, (s, ctx, [id]) => [201, s.addMember(ctx.actor, id, ctx.body)]],
  ['POST', /^\/groups\/([^/]+)\/expenses$/, (s, ctx, [id]) => [201, s.addExpense(ctx.actor, id, ctx.body)]],
  ['GET', /^\/groups\/([^/]+)\/expenses$/, (s, ctx, [id]) => [200, s.listExpenses(ctx.actor, id)]],
  ['GET', /^\/groups\/([^/]+)\/balances$/, (s, ctx, [id]) => [200, s.getBalances(ctx.actor, id)]],
  ['GET', /^\/groups\/([^/]+)\/settle-up$/, (s, ctx, [id]) => [200, s.settleUp(ctx.actor, id)]],
];

export function createApp(service = new ExpenseService()) {
  return createServer(async (req, res) => {
    try {
      const { pathname } = new URL(req.url, 'http://localhost');
      const matching = routes
        .map(([method, pattern, handler]) => ({ method, handler, match: pattern.exec(pathname) }))
        .filter((r) => r.match);
      if (matching.length === 0) throw new ApiError(404, 'not_found', 'route not found');
      const route = matching.find((r) => r.method === req.method);
      if (!route) {
        res.setHeader('Allow', matching.map((r) => r.method).join(', '));
        throw new ApiError(405, 'method_not_allowed', 'method not allowed');
      }

      const ctx = {
        actor: req.headers['x-user-id'],
        body: req.method === 'POST' ? await readJson(req) : undefined,
      };
      const params = route.match.slice(1).map(decodePathSegment);
      const [status, payload] = route.handler(service, ctx, params);
      send(res, status, payload);
    } catch (err) {
      if (err instanceof ApiError) {
        send(res, err.status, { error: { code: err.code, message: err.message } });
      } else {
        console.error(err);
        send(res, 500, { error: { code: 'internal_error', message: 'internal server error' } });
      }
    }
  });
}

function decodePathSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch {
    throw new ApiError(404, 'not_found', 'route not found');
  }
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new ApiError(413, 'payload_too_large', 'request body too large');
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString('utf8');
  if (raw.trim() === '') return {};
  let body;
  try {
    body = JSON.parse(raw);
  } catch {
    throw new ApiError(400, 'invalid_json', 'request body must be valid JSON');
  }
  if (body === null || typeof body !== 'object' || Array.isArray(body)) {
    throw new ApiError(400, 'invalid_json', 'request body must be a JSON object');
  }
  return body;
}

function send(res, status, payload) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(payload));
}
