---
description: De-brand + configure a freshly-exported Lovable app (tests, deps, tokensave, Railway/GitHub).
argument-hint: "[project-dir] (default: current dir)"
---

Run the bundled `lovable-setup` script on the target Lovable project.

- Target dir: `$ARGUMENTS` if given, else the current working directory.
- Invoke via Bash: `${CLAUDE_PLUGIN_ROOT}/scripts/lovable-setup $ARGUMENTS`
  (self-contained in the plugin, so it travels with `/plugin install` and across
  machines; also on PATH as `lovable-setup` if you ran `bin/install.sh`).
- Interactive: it prompts for in-range dep updates, history squash, GitHub repo
  creation, and Railway setup. Surface its prompts to the user; do not
  auto-answer the destructive steps (history squash, repo creation).
- Idempotent — safe to re-run; every step no-ops if already done.
- After it finishes, relay the summary line and the one manual step it prints
  (GitHub->Railway auto-deploy is OAuth dashboard-only).
