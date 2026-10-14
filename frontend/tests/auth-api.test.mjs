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

test("dataset pagination and bulk actions use scoped API contracts and CSRF", async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
  const originalFetch = globalThis.fetch;
  try {
    const api = await server.ssrLoadModule("/src/api.ts");
    const ids = ["00000000-0000-0000-0000-000000000001"];
    globalThis.fetch = async (url, options) => {
      if (url.endsWith("/auth/login")) return Response.json({ user: {}, csrf_token: "test-csrf" });
      if (url.includes("/datasets/page?")) {
        const query = new URL(url).searchParams;
        assert.equal(query.get("page"), "2");
        assert.equal(query.get("page_size"), "10");
        assert.equal(query.get("search"), "Data & 100%");
        assert.equal(query.get("assessment_status"), "FAILED");
        return Response.json({ items: [], total: 0, page: 2, page_size: 10 });
      }
      assert.ok(url.endsWith("/datasets/bulk-delete") || url.endsWith("/datasets/bulk-restore"));
      assert.equal(options.method, "POST");
      assert.equal(options.headers.get("x-csrf-token"), "test-csrf");
      assert.deepEqual(JSON.parse(options.body), { dataset_ids: ids });
      return Response.json({ dataset_ids: ids, count: 1 });
    };
    await api.loginLocal("test.user", "test-password");
    assert.equal((await api.getDatasetPage(2, 10, "Data & 100%", "FAILED")).page, 2);
    assert.equal((await api.deleteDatasets(ids)).count, 1);
    assert.equal((await api.restoreDatasets(ids)).count, 1);
  } finally { globalThis.fetch = originalFetch; await server.close(); }
});

test("optional role confirmation sends CSRF and revision without uploading source", async () => {
  const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
  const originalFetch = globalThis.fetch;
  try {
    const api = await server.ssrLoadModule("/src/api.ts");
    globalThis.fetch = async (url, options) => {
      if (url.endsWith("/auth/me")) return Response.json({ user: {}, csrf_token: "test-csrf" });
      assert.ok(url.endsWith("/datasets/test-id/column-roles"));
      assert.equal(options.method, "POST");
      assert.equal(options.credentials, "include");
      assert.equal(options.headers.get("x-csrf-token"), "test-csrf");
      assert.deepEqual(JSON.parse(options.body), { roles: { nilai: "identifier" }, expected_revision: 2 });
      return Response.json({ id: "test-id" });
    };
    await api.getCurrentUser();
    assert.equal((await api.updateColumnRoles("test-id", { nilai: "identifier" }, 2)).id, "test-id");
  } finally { globalThis.fetch = originalFetch; await server.close(); }
});
