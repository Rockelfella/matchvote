#!/usr/bin/env node
/**
 * Dry-run: create branch + placeholder commit + draft PR from an Issue trigger.
 * No AI patch generation yet.
 */
const { execSync } = require("node:child_process");

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

const repo = mustEnv("REPO");
const issueNumber = mustEnv("ISSUE_NUMBER");
const actor = mustEnv("ACTOR");

const branch = `ai/issue-${issueNumber}`;
const title = `AI (dry-run): Issue #${issueNumber}`;
const body = [
  `Triggered by: @${actor}`,
  ``,
  `This is a **dry-run draft PR**.`,
  `Next step (v2): generate an actual patch via AI and update this PR.`,
  ``,
  `- Source issue: #${issueNumber}`,
].join("\n");

try {
  sh(`git config user.name "github-actions[bot]"`);
  sh(`git config user.email "41898282+github-actions[bot]@users.noreply.github.com"`);

  const defaultBranch = sh(`git remote show origin | sed -n '/HEAD branch/s/.*: //p'`);
  sh(`git fetch origin ${defaultBranch} --depth=1`);

  sh(`git checkout -B ${branch} origin/${defaultBranch}`);

  const markerPath = `.ai/DRY_RUN_ISSUE_${issueNumber}.md`;
  sh(`mkdir -p .ai`);
  sh(`bash -lc 'cat > ${markerPath} <<EOF
# AI Dry Run

This file is a placeholder created by the GitHub Action.

- Issue: #${issueNumber}
- Branch: ${branch}

EOF'`);

  sh(`git add ${markerPath}`);

  const status = sh(`git status --porcelain`);
  if (status.length > 0) {
    sh(`git commit -m "chore(ai): dry-run placeholder for issue #${issueNumber}"`);
    sh(`git push -u origin ${branch} --force`);
  } else {
    sh(`git push -u origin ${branch} --force`);
  }

  const existing = sh(
    `gh pr list --repo ${repo} --head ${branch} --json number --jq '.[0].number' || true`
  );
  if (existing) {
    console.log(`PR already exists: #${existing}`);
    process.exit(0);
  }

  sh(
    `gh pr create --repo ${repo} --head ${branch} --base ${defaultBranch} --draft --title "${title}" --body "${body.replace(/"/g, '\\"')}"`
  );

  console.log("Draft PR created.");
} catch (err) {
  console.error(err?.message || err);
  process.exit(1);
}
