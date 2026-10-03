import { beforeEach, describe, expect, it } from "vitest";
import type { FastifyInstance } from "fastify";
import { newApp } from "./helpers.js";

let app: FastifyInstance;

beforeEach(() => {
  app = newApp();
});

const unknownId = "00000000-0000-4000-8000-000000000000";

describe("POST /groups", () => {
  it("creates a group with initial members", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/groups",
      payload: { name: "Trip", members: ["Alice", "Bob"] },
    });
    expect(response.statusCode).toBe(201);
    const body = response.json();
    expect(body).toEqual({
      id: expect.any(String),
      name: "Trip",
      members: [
        { id: expect.any(String), name: "Alice" },
        { id: expect.any(String), name: "Bob" },
      ],
    });
    expect(body.members[0].id).not.toBe(body.members[1].id);
  });

  it("creates a group without members", async () => {
    const response = await app.inject({ method: "POST", url: "/groups", payload: { name: "Flat" } });
    expect(response.statusCode).toBe(201);
    expect(response.json().members).toEqual([]);
  });

  it.each([{}, { name: "" }, { name: "   " }, { name: 5 }])("rejects invalid name %j with 400", async (payload) => {
    const response = await app.inject({ method: "POST", url: "/groups", payload });
    expect(response.statusCode).toBe(400);
    expect(response.json().error.code).toBe("VALIDATION_ERROR");
  });

  it("rejects duplicate initial member names with 409 and creates nothing", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/groups",
      payload: { name: "Trip", members: ["Bob", "BOB"] },
    });
    expect(response.statusCode).toBe(409);
    expect(response.json().error.code).toBe("CONFLICT");
  });
});

describe("POST /groups/:groupId/members", () => {
  it("adds a member that then appears in GET", async () => {
    const group = (await app.inject({ method: "POST", url: "/groups", payload: { name: "Trip" } })).json();
    const response = await app.inject({
      method: "POST",
      url: `/groups/${group.id}/members`,
      payload: { name: "Carol" },
    });
    expect(response.statusCode).toBe(201);
    const carol = response.json();
    expect(carol).toEqual({ id: expect.any(String), name: "Carol" });

    const fetched = await app.inject({ method: "GET", url: `/groups/${group.id}` });
    expect(fetched.json().members).toEqual([carol]);
  });

  it("returns 404 for an unknown group", async () => {
    const response = await app.inject({
      method: "POST",
      url: `/groups/${unknownId}/members`,
      payload: { name: "Carol" },
    });
    expect(response.statusCode).toBe(404);
    expect(response.json().error.code).toBe("NOT_FOUND");
  });

  it("rejects a duplicate name (case-insensitive, trimmed) with 409", async () => {
    const group = (
      await app.inject({ method: "POST", url: "/groups", payload: { name: "Trip", members: ["Alice"] } })
    ).json();
    const response = await app.inject({
      method: "POST",
      url: `/groups/${group.id}/members`,
      payload: { name: " alice " },
    });
    expect(response.statusCode).toBe(409);
    const fetched = await app.inject({ method: "GET", url: `/groups/${group.id}` });
    expect(fetched.json().members).toHaveLength(1);
  });

  it("rejects a blank member name with 400", async () => {
    const group = (await app.inject({ method: "POST", url: "/groups", payload: { name: "Trip" } })).json();
    const response = await app.inject({
      method: "POST",
      url: `/groups/${group.id}/members`,
      payload: { name: " " },
    });
    expect(response.statusCode).toBe(400);
  });
});

describe("GET /groups/:groupId", () => {
  it("returns an existing group", async () => {
    const created = (
      await app.inject({ method: "POST", url: "/groups", payload: { name: "Trip", members: ["Alice"] } })
    ).json();
    const response = await app.inject({ method: "GET", url: `/groups/${created.id}` });
    expect(response.statusCode).toBe(200);
    expect(response.json()).toEqual(created);
  });

  it("returns 404 for an unknown group", async () => {
    const response = await app.inject({ method: "GET", url: `/groups/${unknownId}` });
    expect(response.statusCode).toBe(404);
    expect(response.json()).toEqual({ error: { code: "NOT_FOUND", message: expect.any(String) } });
  });
});
