import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "vite";

test("logout accepts a successful empty response", async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
  const originalFetch = globalThis.fetch;
  try {
    const api = await server.ssrLoadModule("/src/api.ts");
    globalThis.fetch = async (url, options) => {
      assert.ok(url.endsWith("/auth/logout"));
      assert.equal(options.method, "POST");
      assert.equal(options.credentials, "include");
      return new Response(null, { status: 204 });
    };
    assert.equal(await api.logoutLocal(), undefined);
  } finally {
    globalThis.fetch = originalFetch;
    await server.close();
  }
});
