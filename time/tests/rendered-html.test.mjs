import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("build contains final Time metadata and hosting identity", async () => {
  const [serverBundle, hostingManifest] = await Promise.all([
    readFile(new URL("../dist/server/index.js", import.meta.url), "utf8"),
    readFile(new URL("../dist/.openai/hosting.json", import.meta.url), "utf8"),
  ]);

  assert.match(serverBundle, /Time — مدیریت نوبت و مشتریان/);
  assert.doesNotMatch(serverBundle, /codex-preview/);

  const hosting = JSON.parse(hostingManifest);
  assert.equal(hosting.d1, "DB");
  assert.equal(hosting.project_id, "appgprj_6a8d740099248191b6179127b546f1c8");
});
