---
description: De-brand + configure a freshly-exported Lovable app (tests, deps, Railway/GitHub).
argument-hint: "[project-dir] (default: current dir)"
---

Run the `lovable-setup` script on the target Lovable project.

- Target dir: `$ARGUMENTS` if given, else the current working directory.
- Invoke it via Bash: `lovable-setup $ARGUMENTS` (it's symlinked onto PATH at `~/bin`).
- The script is interactive (it prompts for in-range dep updates, history squash,
  GitHub repo creation, Railway setup). Surface its prompts to the user; do not
  auto-answer destructive steps (history squash, repo creation) on their behalf.
- It is idempotent — safe to re-run; every step no-ops if already done.
- After it finishes, relay the summary line and the one manual step it prints
  (GitHub→Railway auto-deploy is OAuth dashboard-only).
