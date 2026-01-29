#!/usr/bin/env node
/**
 * Apply: generate AI JSON, write allowlisted files, commit, and update draft PR.
 */
const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
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

function extractJsonText(responseJson) {
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

function parseCommand(raw) {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return "";
  const parts = trimmed.split(/\s+/);
  if (parts[0] !== "/ai") return "";
  if (parts.length === 1) return "/ai";
  if (parts.length === 2 && parts[1] === "apply") return "/ai apply";
  return "";
}

function escapeBody(body) {
  return String(body).replace(/`/g, "\\`").replace(/"/g, '\\"');
}

function commentIssue(repo, issueNumber, body) {
  sh(
    `gh issue comment ${issueNumber} --repo ${repo} --body "${escapeBody(body)}"`
  );
}

function commentPr(repo, prNumber, body) {
  sh(`gh pr comment ${prNumber} --repo ${repo} --body "${escapeBody(body)}"`);
}

function isSafePath(p) {
  if (!p || typeof p !== "string") return false;
  if (p.includes("..")) return false;
  if (path.isAbsolute(p)) return false;
  return true;
}

async function main() {
  const repo = mustEnv("REPO");
  const issueNumber = mustEnv("ISSUE_NUMBER");
  const aiKey = mustEnv("AI_API_KEY");
  const commentBody = process.env.COMMENT_BODY || "";

  const cmd = parseCommand(commentBody);
  if (cmd !== "/ai apply") {
    process.exit(0);
  }

  const labels = sh(
    `gh api repos/${repo}/issues/${issueNumber} --jq '.labels[].name' || true`
  );
  if (!labels.split(/\r?\n/).includes("ai-processed")) {
    commentIssue(
      repo,
      issueNumber,
      "Please run /ai first (dry-run) before /ai apply."
    );
    process.exit(0);
  }

  const branch = `ai/issue-${issueNumber}`;
  const prNumber = sh(
    `gh pr list --repo ${repo} --head ${branch} --json number --jq '.[0].number'`
  );
  if (!prNumber) {
    console.error(`No PR found for branch ${branch}`);
    process.exit(1);
  }

  const lockDir = path.join(".ai", "locks");
  const lockPath = path.join(lockDir, `issue-${issueNumber}.lock`);
  fs.mkdirSync(lockDir, { recursive: true });
  if (fs.existsSync(lockPath)) {
    const raw = fs.readFileSync(lockPath, "utf8").trim();
    const last = Number(raw);
    if (Number.isFinite(last)) {
      const deltaMs = Date.now() - last;
      if (deltaMs < 2 * 60 * 1000) {
        commentIssue(repo, issueNumber, "Cooldown active, try again in 2 minutes.");
        process.exit(0);
      }
    }
  }
  fs.writeFileSync(lockPath, String(Date.now()), "utf8");

  sh(`git config user.name "github-actions[bot]"`);
  sh(`git config user.email "41898282+github-actions[bot]@users.noreply.github.com"`);
  sh(`git fetch origin ${branch} --depth=1`);
  sh(`git checkout ${branch}`);

  const issue = ghJson(`gh api repos/${repo}/issues/${issueNumber}`);
  const issueTitle = issue?.title || "";
  const issueBody = issue?.body || "";

  const allowlist = ["index.html", "web/index.html"];
  const targetPath = "web/index.html";
  if (!fs.existsSync(targetPath)) {
    commentIssue(
      repo,
      issueNumber,
      `Missing required file: ${targetPath}.`
    );
    process.exit(1);
  }
  const currentContent = fs.readFileSync(targetPath, "utf8");

  const prompt = [
    "You are an AI coding assistant.",
    "Return ONLY valid JSON. No markdown, no code fences, no explanations.",
    "JSON schema:",
    "{",
    '  "files": [',
    '    { "path": "web/index.html", "content": "<full file content as string>" }',
    "  ],",
    '  "summary": "short summary",',
    '  "notes": "optional"',
    "}",
    "",
    "Allowed paths: web/index.html only.",
    "Task: remove the API Docs button from the landing page without layout gaps.",
    "",
    `Issue title: ${issueTitle}`,
    "Issue body:",
    issueBody || "(empty)",
    "",
    "Current web/index.html:",
    "-----",
    currentContent,
    "-----",
  ].join("\n");

  const payload = JSON.stringify({
    model: process.env.AI_MODEL || "gpt-4.1-mini",
    input: prompt,
    temperature: 0,
    response_format: { type: "json_object" },
  });

  let response;
  try {
    response = await httpJson(
      "https://api.openai.com/v1/responses",
      {
        Authorization: `Bearer ${aiKey}`,
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payload),
      },
      payload
    );
  } catch (err) {
    const isQuota =
      err?.statusCode === 429 || err?.errorCode === "insufficient_quota";
    if (isQuota) {
      const blockedMsg =
        "AI apply blocked: OpenAI quota/billing exhausted for AI_API_KEY. Please fix billing or update the key, then re-run /ai apply.";
      commentIssue(repo, issueNumber, blockedMsg);
      process.exit(0);
    }
    throw err;
  }

  const rawText = extractJsonText(response);
  const jsonText = rawText.replace(/```json\\s*/gi, "").replace(/```/g, "");
  let parsed;
  try {
    parsed = JSON.parse(jsonText);
  } catch (err) {
    commentIssue(
      repo,
      issueNumber,
      "AI response was not valid JSON. Please refine the issue and try again."
    );
    process.exit(0);
  }

  const files = Array.isArray(parsed?.files) ? parsed.files : [];
  if (files.length === 0) {
    commentIssue(
      repo,
      issueNumber,
      "AI response contained no files to write."
    );
    process.exit(0);
  }

  for (const file of files) {
    if (!isSafePath(file?.path)) {
      commentIssue(
        repo,
        issueNumber,
        "AI response contained an unsafe file path."
      );
      process.exit(0);
    }
    if (!allowlist.includes(file.path)) {
      commentIssue(
        repo,
        issueNumber,
        `AI response attempted to write a non-allowlisted path: ${file.path}.`
      );
      process.exit(0);
    }
    if (typeof file.content !== "string") {
      commentIssue(
        repo,
        issueNumber,
        `AI response had non-string content for ${file.path}.`
      );
      process.exit(0);
    }
  }

  for (const file of files) {
    const dir = path.dirname(file.path);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(file.path, file.content, "utf8");
  }

  const diffStat = sh("git diff --stat");
  if (!diffStat.trim()) {
    commentIssue(
      repo,
      issueNumber,
      "No changes detected after applying AI output."
    );
    process.exit(1);
  }

  const changed = sh("git diff --name-only").split(/\r?\n/).filter(Boolean);
  sh(`git add ${changed.join(" ")}`);
  sh(`git commit -m "chore(ui): remove API Docs button from landing page"`);
  sh(`git push -u origin ${branch}`);

  const summary = typeof parsed?.summary === "string" && parsed.summary.trim()
    ? parsed.summary.trim()
    : "Removed API Docs button from landing page.";
  const notes = typeof parsed?.notes === "string" && parsed.notes.trim()
    ? parsed.notes.trim()
    : "";
  const prComment = [
    `Summary: ${summary}`,
    notes ? "" : null,
    notes ? `Notes: ${notes}` : null,
  ]
    .filter(Boolean)
    .join("\n");
  commentPr(repo, prNumber, prComment);
}

main().catch((err) => {
  console.error(err?.message || err);
  process.exit(1);
});
