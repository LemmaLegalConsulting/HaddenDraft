import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { expect, test } from "@playwright/test";

import { apiCall, guardNetwork, modelTimeout, openScreen, signIn } from "./support/deployment.js";

// The argument gym: upload a brief, run the opponent/judge/coach passes on a
// background thread, and work through the challenges. The run outlives any
// single request -- that is the point of running it in the background -- so
// this polls the run the way the panel does.

const briefs = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "sample_briefs");
const DEFECTIVE_BRIEF = join(briefs, "03_defective_brief_unsupported_retaliation_and_habitability_hamilton.docx");
const runTimeout = Number(process.env.E2E_GYM_RUN_TIMEOUT_MS || 15 * 60_000);

test.describe("argument gym", () => {
  test("a brief is uploaded, run, and its challenges can be dispositioned", async ({ page }) => {
    test.setTimeout(runTimeout + modelTimeout * 2);
    const guard = guardNetwork(page);
    await signIn(page);
    await openScreen(page, "Argument gym");
    await page.getByRole("button", { name: "New" }).click();

    let workspaceId;
    await test.step("upload the brief under test", async () => {
      const uploaded = page.waitForResponse((response) =>
        /\/argument-gym\/workspaces\/\d+\/documents\/$/.test(new URL(response.url()).pathname),
      );
      await page.locator("label.gym-upload input[type=file]").setInputFiles(DEFECTIVE_BRIEF);
      const response = await uploaded;
      expect(response.ok(), `upload answered ${response.status()}`).toBeTruthy();
      workspaceId = Number(new URL(response.url()).pathname.match(/workspaces\/(\d+)\//)[1]);
      await expect(page.locator(".gym-brief-name")).toContainText(/addressable passages/);
    });

    await test.step("choose no case record and the default checks", async () => {
      await page.getByRole("radio", { name: /No case record/ }).check();
      await expect(page.locator("details.gym-config summary", { hasText: "Checks to run" })).toContainText(/Checks to run\s*\d+ of \d+ selected/);
    });

    let runId;
    await test.step("the run starts in the background and answers at once", async () => {
      const started = page.waitForResponse(
        (response) => /\/workspaces\/\d+\/runs\/$/.test(new URL(response.url()).pathname) && response.request().method() === "POST",
      );
      await page.getByRole("button", { name: "Run the gym" }).click();
      const response = await started;
      // 202 and a row to poll, never a request held open for the whole run.
      expect(response.status()).toBe(202);
      runId = (await response.json()).run.id;
    });

    await test.step("the run finishes", async () => {
      await expect
        .poll(async () => (await apiCall(page, "GET", `/argument-gym/runs/${runId}/`)).data.run.status, {
          timeout: runTimeout,
          intervals: [5_000, 10_000],
        })
        .toMatch(/^(complete|failed)$/);
      const run = (await apiCall(page, "GET", `/argument-gym/runs/${runId}/`)).data.run;
      expect(run.status, run.error || "").toBe("complete");
      expect(run.challenges?.length ?? 0, "a defective brief draws challenges").toBeGreaterThan(0);
      await expect(page.locator("article.gym-challenge").first()).toBeVisible({ timeout: 60_000 });
    });

    await test.step("a challenge is dispositioned and the choice sticks", async () => {
      const challenge = page.locator("article.gym-challenge").first();
      const saved = page.waitForResponse((response) => /\/argument-gym\/challenges\/\d+\/$/.test(new URL(response.url()).pathname));
      await challenge.getByRole("button", { name: "Addressed" }).click();
      expect((await saved).ok()).toBeTruthy();
      const run = (await apiCall(page, "GET", `/argument-gym/runs/${runId}/`)).data.run;
      expect(run.challenges.some((item) => item.disposition === "addressed")).toBeTruthy();
    });

    await test.step("the run's artifacts are served", async () => {
      const run = (await apiCall(page, "GET", `/argument-gym/runs/${runId}/`)).data.run;
      for (const kind of (run.artifacts || []).map((item) => item.kind).slice(0, 3)) {
        const artifact = await apiCall(page, "GET", `/argument-gym/runs/${runId}/artifacts/${kind}/`);
        expect(artifact.status, `artifact ${kind}`).toBe(200);
      }
    });

    await test.step("the workspace is deleted", async () => {
      const deleted = await apiCall(page, "DELETE", `/argument-gym/workspaces/${workspaceId}/`);
      expect(deleted.ok).toBeTruthy();
      const gone = await apiCall(page, "GET", `/argument-gym/workspaces/${workspaceId}/`);
      expect(gone.status).toBe(404);
    });
    guard.assertClean();
  });

  test("checklists can be created, edited, and deleted", async ({ page }) => {
    const guard = guardNetwork(page);
    await signIn(page);
    const name = `E2E checklist ${Date.now()}`;
    const created = await apiCall(page, "POST", "/argument-gym/checklists/", {
      title: name,
      items: [{ text: "Every factual assertion cites the record." }],
    });
    expect(created.ok, JSON.stringify(created.data).slice(0, 300)).toBeTruthy();
    const id = created.data.checklist.id;
    const updated = await apiCall(page, "PATCH", `/argument-gym/checklists/${id}/`, { title: `${name} (edited)` });
    expect(updated.ok).toBeTruthy();
    const listed = await apiCall(page, "GET", "/argument-gym/checklists/");
    expect(JSON.stringify(listed.data)).toContain(`${name} (edited)`);
    const deleted = await apiCall(page, "DELETE", `/argument-gym/checklists/${id}/`);
    expect(deleted.ok).toBeTruthy();
    guard.assertClean();
  });

  test("courts and legal rules load, and every rule states its verification", async ({ page }) => {
    await signIn(page);
    const courts = await apiCall(page, "GET", "/argument-gym/courts/");
    expect(courts.status).toBe(200);
    expect((courts.data.courts || []).length).toBeGreaterThan(0);
    const rules = await apiCall(page, "GET", "/argument-gym/legal-rules/");
    expect(rules.status).toBe(200);
    for (const rule of rules.data.rules || []) {
      expect(rule.verification, `${rule.slug || rule.name} states its verification`).toBeTruthy();
    }
    const checks = await apiCall(page, "GET", "/argument-gym/checks/");
    expect(checks.status).toBe(200);
    expect((checks.data.checks || []).length).toBeGreaterThan(0);
  });
});
