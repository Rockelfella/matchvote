# MatchVote “Operated using RS Digital Engineering methodology.”

MatchVote is a football fan engagement platform that allows users to rate and discuss match scenes
(goals, fouls, cards, decisions) in near real time.

This repository contains the full technical implementation of the MatchVote system.

---

## Repository Structure

- `api/`  
  Backend service (FastAPI, PostgreSQL, background jobs, integrations)

- `venv/`  
  Python virtual environment (local / server only, not versioned)

- `.gitignore`  
  Git exclusions for virtualenvs, caches, logs, secrets

- `DEPLOYMENT.md`  
  Notes and instructions for deployment and server operation

- `LICENSES.md`  
  Third-party licenses and dependency notes

---

## Development Principles
- Operated using RS Digital Engineering methodology
- Private repository (no public API exposure by default)
- SSH-based access (no tokens in git)
- Server is deployment target, GitHub is source of truth
- Changes are reviewed via commits and pull requests
- Agent-assisted development is used as a tool, not as an authority

---

## Deployment Model (Current)

- GitHub hosts the canonical repository
- Vultr server pulls via SSH deploy key
- Services are managed via systemd
- Secrets are injected via environment variables (never committed)

---

## Status

This repository is under active development.
Structure, tooling and workflows are intentionally kept explicit and auditable.

---

---

## Engineering Methodology

MatchVote is operated using **RS Digital Engineering** methodology (human-owned, auditable Agent-Driven Development).
Reference: https://github.com/rs-digital-engineering/foundation
