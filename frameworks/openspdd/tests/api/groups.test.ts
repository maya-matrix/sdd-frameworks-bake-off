import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildApp } from '../../src/app.js';
import { addMember, createGroup } from './helpers.js';

let app: FastifyInstance;

beforeEach(() => {
  app = buildApp();
});

afterEach(async () => {
  await app.close();
});

describe('groups', () => {
  it('creates a group', async () => {
    const res = await app.inject({ method: 'POST', url: '/groups', payload: { name: '  Trip  ' } });
    expect(res.statusCode).toBe(201);
    const body = res.json();
    expect(body).toMatchObject({ name: 'Trip', members: [] });
    expect(body.id).toMatch(/^[0-9a-f-]{36}$/);

    const fetched = await app.inject({ method: 'GET', url: `/groups/${body.id}` });
    expect(fetched.statusCode).toBe(200);
    expect(fetched.json()).toEqual(body);
  });

  it.each([{}, { name: '' }, { name: '   ' }, { name: 'x'.repeat(101) }])(
    'rejects invalid body %j with 400',
    async (payload) => {
      const res = await app.inject({ method: 'POST', url: '/groups', payload });
      expect(res.statusCode).toBe(400);
      expect(res.json().error.code).toBe('VALIDATION_ERROR');
    },
  );

  it('rejects unknown properties with 400', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/groups',
      payload: { name: 'Trip', extra: true },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe('VALIDATION_ERROR');
  });

  it('rejects malformed JSON with 400', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/groups',
      headers: { 'content-type': 'application/json' },
      payload: '{"name":',
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error.code).toBe('VALIDATION_ERROR');
  });

  it('returns 404 GROUP_NOT_FOUND for an unknown group', async () => {
    const res = await app.inject({ method: 'GET', url: '/groups/nope' });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toEqual({
      error: { code: 'GROUP_NOT_FOUND', message: 'Group not found', details: { groupId: 'nope' } },
    });
  });

  it('returns 404 ROUTE_NOT_FOUND for an unknown route', async () => {
    const res = await app.inject({ method: 'GET', url: '/nowhere' });
    expect(res.statusCode).toBe(404);
    expect(res.json().error.code).toBe('ROUTE_NOT_FOUND');
  });
});

describe('members', () => {
  it('adds members and lists them in insertion order', async () => {
    const groupId = await createGroup(app);
    const res = await app.inject({
      method: 'POST',
      url: `/groups/${groupId}/members`,
      payload: { name: ' Alice ' },
    });
    expect(res.statusCode).toBe(201);
    expect(res.json()).toMatchObject({ name: 'Alice' });
    await addMember(app, groupId, 'Bob');
    await addMember(app, groupId, 'Carol');

    const list = await app.inject({ method: 'GET', url: `/groups/${groupId}/members` });
    expect(list.statusCode).toBe(200);
    expect(list.json().members.map((m: { name: string }) => m.name)).toEqual(['Alice', 'Bob', 'Carol']);

    const group = await app.inject({ method: 'GET', url: `/groups/${groupId}` });
    expect(group.json().members).toHaveLength(3);
  });

  it('rejects a duplicate name case-insensitively with 409', async () => {
    const groupId = await createGroup(app);
    await addMember(app, groupId, 'Alice');
    const res = await app.inject({
      method: 'POST',
      url: `/groups/${groupId}/members`,
      payload: { name: 'aLiCe ' },
    });
    expect(res.statusCode).toBe(409);
    expect(res.json().error.code).toBe('DUPLICATE_MEMBER_NAME');
  });

  it('allows the same name in different groups', async () => {
    const g1 = await createGroup(app);
    const g2 = await createGroup(app);
    await addMember(app, g1, 'Alice');
    const res = await app.inject({ method: 'POST', url: `/groups/${g2}/members`, payload: { name: 'Alice' } });
    expect(res.statusCode).toBe(201);
  });

  it('returns 404 when adding to or listing an unknown group', async () => {
    const add = await app.inject({ method: 'POST', url: '/groups/nope/members', payload: { name: 'A' } });
    expect(add.statusCode).toBe(404);
    const list = await app.inject({ method: 'GET', url: '/groups/nope/members' });
    expect(list.statusCode).toBe(404);
  });
});
