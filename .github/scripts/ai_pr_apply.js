#!/usr/bin/env node
/**
 * Apply: generate AI patch, apply, commit, and update draft PR.
 */
const { execSync } = require("node:child_process");
const fs = require("node:fs");
const https = require("node:https");

function sh(cmd) {
  return execSync(cmd, { stdio: "pipe", encoding: "utf8" }).trim();
}

function mustEnv(name) {
  const v = process.env[name];
  if (!v) {
    console.error(`Missing env var: ${name}`);
    process.exit(1);
  }
  return v;
}

function ghJson(cmd) {
  const out = sh(cmd);
  return JSON.parse(out);
}

function httpJson(url, headers, body) {
  return new Promise((resolve, reject) => {
    const req = https.request(url, { method: "POST", headers }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          let parsed = null;
          try {
            parsed = JSON.parse(data);
          } catch (_) {
            parsed = null;
          }
          const err = new Error(`AI API error: ${res.statusCode} ${data}`);
          err.statusCode = res.statusCode;
          err.body = data;
          err.errorCode = parsed?.error?.code;
          reject(err);
          return;
        }
        try {
          resolve(JSON.parse(data));
        } catch (err) {
          reject(err);
        }
      });
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

function extractDiffText(responseJson) {
  if (responseJson && typeof responseJson.output_text === "string") {
    return responseJson.output_text.trim();
  }
  if (Array.isArray(responseJson?.output)) {
    const chunks = [];
    for (const item of responseJson.output) {
      if (!Array.isArray(item?.content)) continue;
      for (const c of item.content) {
        if (typeof c?.text === "string") chunks.push(c.text);
      }
    }
    return chunks.join("").trim();
  }
  return "";
}

function extractUnifiedDiff(rawText) {
  if (!rawText) return "";
  const cleaned = rawText.replace(/```diff\s*/g, "").replace(/```\s*/g, "");
  const idx = cleaned.indexOf("diff --git ");
  if (idx === -1) return "";
  return cleaned.slice(idx).trim();
}

function isProbablyValidDiff(diffText) {
  if (!diffText) return false;
  const lines = diffText.split(/\r?\n/);
  const hasDiff = lines.some((l) => l.startsWith("diff --git "));
  const hasMinus = lines.some((l) => l.startsWith("--- "));
  const hasPlus = lines.some((l) => l.startsWith("+++ "));
  if (!hasDiff || !hasMinus || !hasPlus) return false;
  const lower = diffText.toLowerCase();
  if (lower.includes("here is") || lower.includes("sure") || lower.includes("explanation:")) {
    return false;
  }
  return true;
}

function getTouchedFiles(diffText) {
  const files = new Set();
  const lines = diffText.split(/\r?\n/);
  for (const line of lines) {
    if (line.startsWith("+++ b/")) {
      const p = line.slice("+++ b/".length).trim();
      if (p && p !== "/dev/null") files.add(p);
    }
  }
  return Array.from(files);
}

function isAllowlisted(path, allowPrefixes) {
  return allowPrefixes.some((p) => path.startsWith(p));
}

function isDenylisted(path, denyPrefixes, allowPackageLock) {
  if (denyPrefixes.some((p) => path.startsWith(p))) return true;
  if (path === ".env" || path.startsWith(".env.")) return true;
  if (!allowPackageLock && path === "package-lock.json") return true;
  if (/(^|\/)secrets(\/|$)/i.test(path)) return true;
  return false;
}

function escapeBody(body) {
  return String(body).replace(/`/g, "\\`").replace(/"/g, '\\"');
}

async function main() {
  const repo = mustEnv("REPO");
  const issueNumber = mustEnv("ISSUE_NUMBER");
  const actor = mustEnv("ACTOR");
  mustEnv("GITHUB_TOKEN");
  const aiKey = mustEnv("AI_API_KEY");

  const branch = `ai/issue-${issueNumber}`;

  const issue = ghJson(`gh api repos/${repo}/issues/${issueNumber}`);
  const issueTitle = issue?.title || "";
  const issueBody = issue?.body || "";

  const prNumber = sh(
    `gh pr list --repo ${repo} --head ${branch} --json number --jq '.[0].number'`
  );
  if (!prNumber) {
    console.error(`No PR found for branch ${branch}`);
    process.exit(1);
  }

  const defaultBranch = sh(`gh api repos/${repo} --jq .default_branch`);
  const defaultRef = sh(
    `gh api repos/${repo}/git/refs/heads/${defaultBranch} --jq .object.sha`
  );
  const tree = ghJson(
    `gh api repos/${repo}/git/trees/${defaultRef}?recursive=1`
  );

  const allowPrefixes = ["app/", "api/", "src/", "web/", "migrations/", "docs/"];
  const denyPrefixes = [".github/workflows/", ".github/scripts/", "node_modules/"];
  const allowPackageLock = /package-lock\.json/i.test(
    `${issueTitle}\n${issueBody}`
  );

  const allowedTree = (tree?.tree || [])
    .filter((t) => t.type === "blob")
    .map((t) => t.path)
    .filter((p) => isAllowlisted(p, allowPrefixes))
    .filter((p) => !isDenylisted(p, denyPrefixes, allowPackageLock))
    .sort();

  const prompt = [
    `You are an AI coding assistant. Return ONLY a unified diff (git patch).`,
    `No explanations.`,
    ``,
    `Issue title: ${issueTitle}`,
    `Issue body:`,
    issueBody || "(empty)",
    ``,
    `Allowed paths: ${allowPrefixes.join(", ")}`,
    `Deny paths: .github/workflows/, .github/scripts/, .env, secrets, node_modules/, package-lock.json`,
    ``,
    `Repository files (allowed only):`,
    ...allowedTree.map((p) => `- ${p}`),
    ``,
    `Constraints:`,
    `- Touch only allowlisted paths.`,
    `- Do not touch denylisted paths.`,
    `- Output ONLY the diff.`,
  ].join("\n");

  const payload = JSON.stringify({
    model: process.env.AI_MODEL || "gpt-4.1-mini",
    input: prompt,
    temperature: 0,
  });

  let response;
  try {
    response = await httpJson("https://api.openai.com/v1/responses", {
      Authorization: `Bearer ${aiKey}`,
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(payload),
    }, payload);
  } catch (err) {
    const isQuota =
      err?.statusCode === 429 || err?.errorCode === "insufficient_quota";
    if (isQuota) {
      console.error("AI apply blocked: OpenAI quota/billing exhausted.");
      const blockedMsg =
        "🚫 AI apply blocked: OpenAI quota/billing exhausted for AI_API_KEY. Please fix billing or update the key, then re-run /ai apply.";
      sh(
        `gh issue comment ${issueNumber} --repo ${repo} --body "${blockedMsg.replace(/"/g, '\\"')}"`
      );
      if (prNumber) {
        sh(
          `gh pr comment ${prNumber} --repo ${repo} --body "${blockedMsg.replace(/"/g, '\\"')}"`
        );
      }
      sh(
        `gh issue edit ${issueNumber} --repo ${repo} --add-label "ai-blocked" || true`
      );
      process.exit(0);
    }
    throw err;
  }

  const rawText = extractDiffText(response);
  const diffText = extractUnifiedDiff(rawText);
  if (!diffText || !isProbablyValidDiff(diffText)) {
    const snippet = rawText
      .split(/\r?\n/)
      .slice(0, 40)
      .join("\n");
    const msg =
      "🚫 AI produced an invalid patch format (corrupt/unified diff missing). Please refine the issue or re-run /ai apply. The PR was not changed.";
    const details = [
      "<details>",
      "<summary>Raw AI output (first ~40 lines)</summary>",
      "",
      "```",
      snippet,
      "```",
      "</details>",
    ].join("\n");
    sh(
      `gh issue comment ${issueNumber} --repo ${repo} --body "${escapeBody(`${msg}\n\n${details}`)}"`
    );
    if (prNumber) {
      sh(
        `gh pr comment ${prNumber} --repo ${repo} --body "${escapeBody(`${msg}\n\n${details}`)}"`
      );
    }
    process.exit(0);
  }
  const maxBytes = 200_000;
  if (Buffer.byteLength(diffText, "utf8") > maxBytes) {
    console.error("AI diff exceeds size limit");
    process.exit(1);
  }

  const touchedFiles = getTouchedFiles(diffText);
  if (touchedFiles.length === 0) {
    console.error("AI diff touches no files");
    process.exit(1);
  }

  for (const file of touchedFiles) {
    if (!isAllowlisted(file, allowPrefixes)) {
      console.error(`Diff touches non-allowlisted path: ${file}`);
      process.exit(1);
    }
    if (isDenylisted(file, denyPrefixes, allowPackageLock)) {
      console.error(`Diff touches denylisted path: ${file}`);
      process.exit(1);
    }
  }

  sh(`git config user.name "github-actions[bot]"`);
  sh(`git config user.email "41898282+github-actions[bot]@users.noreply.github.com"`);
  sh(`git fetch origin ${branch} --depth=1`);
  sh(`git checkout ${branch}`);

  sh(`mkdir -p .ai`);
  const patchPath = `.ai/ai_patch_${issueNumber}.diff`;
  fs.writeFileSync(patchPath, diffText, "utf8");

  try {
    sh(`git apply --check ${patchPath}`);
  } catch (err) {
    const out = (err?.stderr || err?.stdout || err?.message || "").toString();
    const msg =
      "🚫 Patch could not be applied cleanly (git apply --check failed). No changes were committed.";
    const details = [
      "<details>",
      "<summary>git apply --check output</summary>",
      "",
      "```",
      out.trim(),
      "```",
      "</details>",
    ].join("\n");
    sh(
      `gh issue comment ${issueNumber} --repo ${repo} --body "${escapeBody(`${msg}\n\n${details}`)}"`
    );
    if (prNumber) {
      sh(
        `gh pr comment ${prNumber} --repo ${repo} --body "${escapeBody(`${msg}\n\n${details}`)}"`
      );
    }
    process.exit(0);
  }

  try {
    sh(`git apply ${patchPath}`);
  } catch (err) {
    console.error(`Patch apply failed: ${err?.message || err}`);
    process.exit(1);
  } finally {
    fs.unlinkSync(patchPath);
  }

  const changed = sh(`git diff --name-only`).split(/\r?\n/).filter(Boolean);
  if (changed.length === 0) {
    console.error("No changes after applying patch");
    process.exit(1);
  }

  sh(`git add ${changed.join(" ")}`);
  const commitMsg = `feat(ai): apply changes for issue #${issueNumber}`;
  sh(`git commit -m "${commitMsg}"`);
  const commitHash = sh(`git rev-parse HEAD`);

  const summaryPath = `.ai/APPLY_SUMMARY.md`;
  const summary = [
    `# AI Apply Summary`,
    ``,
    `- Issue: #${issueNumber}`,
    `- Commit: ${commitHash}`,
    `- Actor: ${actor}`,
    `- Timestamp: ${new Date().toISOString()}`,
    ``,
    `## Files Changed`,
    ...changed.map((f) => `- ${f}`),
    ``,
  ].join("\n");
  fs.writeFileSync(summaryPath, summary, "utf8");
  sh(`git add ${summaryPath}`);
  sh(`git commit -m "chore(ai): add apply summary for issue #${issueNumber}"`);

  sh(`git push -u origin ${branch}`);

  const commentBody = [
    `Applied AI changes for issue #${issueNumber}.`,
    ``,
    `Files changed:`,
    ...changed.map((f) => `- ${f}`),
    ``,
    `Checklist:`,
    `- [ ] Verify changes match the issue requirements`,
    `- [ ] Review for correctness and style`,
    `- [ ] Run tests (if applicable)`,
    ``,
    `Source issue: #${issueNumber}`,
  ].join("\n");
  sh(
    `gh pr comment ${prNumber} --repo ${repo} --body "${commentBody.replace(/"/g, '\\"')}"`
  );
}

main().catch((err) => {
  console.error(err?.message || err);
  process.exit(1);
});
