import { describe, expect, it } from "vitest";
import { buildApp } from "../../src/http/app.js";

describe("error responses", () => {
  it("returns 400 with the error shape for malformed JSON", async () => {
    const app = buildApp();
    const response = await app.inject({
      method: "POST",
      url: "/groups",
      headers: { "content-type": "application/json" },
      payload: "{not json",
    });
    expect(response.statusCode).toBe(400);
    expect(response.json()).toEqual({
      error: { code: "VALIDATION_ERROR", message: expect.any(String) },
    });
  });

  it("returns 404 with the error shape for unknown routes", async () => {
    const app = buildApp();
    const response = await app.inject({ method: "GET", url: "/nope" });
    expect(response.statusCode).toBe(404);
    expect(response.json()).toEqual({ error: { code: "NOT_FOUND", message: expect.any(String) } });
  });

  it("returns 500 without leaking details for unexpected errors", async () => {
    const app = buildApp({
      getGroup: () => {
        throw new Error("secret internals");
      },
    } as never);
    const response = await app.inject({ method: "GET", url: "/groups/x" });
    expect(response.statusCode).toBe(500);
    expect(response.json()).toEqual({ error: { code: "INTERNAL", message: "Internal server error" } });
  });
});
