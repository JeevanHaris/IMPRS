const { test, expect } = require('@playwright/test');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

let temporaryDirectory;
let scanPath;
let proposalId;

test.beforeAll(() => {
  temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'ipmprs-workflow-'));
  scanPath = path.join(temporaryDirectory, 'patrol-note.png');
  const imageScript = [
    'from PIL import Image, ImageDraw, ImageFont',
    'import sys, textwrap',
    'image = Image.new("RGB", (1900, 1100), "white")',
    'draw = ImageDraw.Draw(image)',
    'font = ImageFont.truetype(r"C:\\Windows\\Fonts\\arial.ttf", 48)',
    'text = "PUDUCHERRY POLICE\\nPATROL VEHICLE REQUIREMENT\\nProcurement of patrol cars for North Zone.\\nReplace aging police patrol vehicles. Current maintenance costs are rising.\\nEight GPS equipped police patrol SUVs with emergency lights are requested.\\nEstimated cost: 12000000 rupees. Improve night and highway response coverage."',
    'draw.multiline_text((70, 70), text, fill="black", font=font, spacing=30)',
    'image.save(sys.argv[1])',
  ].join('\n');
  execFileSync('python', ['-c', imageScript, scanPath]);
});

test.afterEach(() => {
  if (!proposalId) return;
  const cleanupScript = [
    'import os, sqlite3, sys',
    'proposal_id = sys.argv[1]',
    'proposal_db = sqlite3.connect("data/proposals.db")',
    'source_rows = proposal_db.execute("SELECT file_path FROM proposal_attachments WHERE proposal_id=?", (proposal_id,)).fetchall()',
    'proposal_db.execute("DELETE FROM proposals WHERE id=?", (proposal_id,))',
    'proposal_db.commit()',
    'proposal_db.close()',
    'for (source_path,) in source_rows:',
    '    if os.path.exists(source_path): os.remove(source_path)',
    'index_db = sqlite3.connect("data/precedents.db")',
    'index_db.execute("DELETE FROM precedent_fts WHERE proposal_id=?", (proposal_id,))',
    'index_db.execute("DELETE FROM precedents WHERE id=?", (proposal_id,))',
    'index_db.commit()',
    'index_db.close()',
  ].join('\n');
  execFileSync('python', ['-c', cleanupScript, proposalId], { cwd: __dirname + '/..' });
  proposalId = null;
});

test.afterAll(() => {
  if (temporaryDirectory) fs.rmSync(temporaryDirectory, { recursive: true, force: true });
});

async function signIn(page, username, password = 'demo123') {
  await page.goto('/workflow');
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

test('scan draft through review, approval, audit, and Word report', async ({ page, browser }) => {
  test.setTimeout(240000);
  await page.goto('/workflow');
  await page.locator('#username').fill('insp.ops');
  await page.locator('#password').fill('wrong-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#error')).toContainText('Invalid username or password.');

  await page.locator('#password').fill('demo123');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.locator('#dashboard')).toBeVisible();
  await page.getByRole('button', { name: 'New proposal' }).click();
  await page.locator('#scan-file').setInputFiles(scanPath);
  const draftResponsePromise = page.waitForResponse(response => response.url().includes('/api/workflow/proposal-ai/draft'));
  await page.getByRole('button', { name: 'Upload scan and draft' }).click();
  const draftResponse = await draftResponsePromise;
  expect(draftResponse.status(), await draftResponse.text()).toBe(201);
  const created = await draftResponse.json();
  proposalId = created.proposal.id;
  expect(created.proposal.status).toBe('Draft');
  await expect(page.locator('#editor')).toBeVisible();
  await expect(page.locator('#similar-alerts')).toContainText('Previously rejected');
  await expect(page.locator('#similar-alerts')).toContainText('Possible active duplicate');
  await expect(page.locator('#similar-results')).toContainText('Approve with Modification');

  await page.locator('#proposal-cost').fill('14000000');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.locator('#detail')).toBeVisible();
  const saved = await page.request.get(`/api/workflow/proposals/${proposalId}`);
  expect((await saved.json()).proposal.estimated_cost).toBe(14000000);
  await page.locator('#decision-remark').fill('Revised cost and supporting quotations attached for review.');
  await page.getByRole('button', { name: 'Submit proposal' }).click();
  await expect(page.locator('#detail-id')).toContainText('Submitted');

  const reviewerContext = await browser.newContext();
  const reviewerPage = await reviewerContext.newPage();
  await signIn(reviewerPage, 'dsp.review');
  await expect(reviewerPage.locator('.proposal').filter({ hasText: proposalId })).toBeVisible();
  await reviewerPage.locator('.proposal').filter({ hasText: proposalId }).getByRole('button', { name: 'Open' }).click();
  await expect(reviewerPage.locator('#detail-precedents')).toBeVisible();
  await expect(reviewerPage.locator('#detail-precedent-results')).toContainText('Rejected on cost');
  await reviewerPage.locator('#decision-remark').fill('Reviewed the cost revision and verified the supporting quotations.');
  await reviewerPage.getByRole('button', { name: 'Start review' }).click();
  await expect(reviewerPage.locator('#detail-id')).toContainText('Under Review');
  await reviewerContext.close();

  const approverContext = await browser.newContext();
  const approverPage = await approverContext.newPage();
  await signIn(approverPage, 'sp.approve');
  await approverPage.locator('.proposal').filter({ hasText: proposalId }).getByRole('button', { name: 'Open' }).click();
  await expect(approverPage.locator('#detail-precedent-results')).toContainText('Approve with Modification');
  await approverPage.locator('#decision-remark').fill('Approved with changes for phased North Zone deployment.');
  await approverPage.getByRole('button', { name: 'Approve' }).click();
  await expect(approverPage.locator('#detail-id')).toContainText('Approved');
  await approverPage.getByRole('button', { name: 'Verify audit trail' }).click();
  await expect(approverPage.locator('#audit-result')).toContainText('Audit trail verified');
  const downloadPromise = approverPage.waitForEvent('download');
  await approverPage.getByRole('button', { name: 'Download Word report' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.docx$/);
  expect(fs.statSync(await download.path()).size).toBeGreaterThan(0);
  await approverContext.close();
});