# obsidian-weaver review fixes — implementation plan

Fixes the P0/P1/P2 findings from the ce-review of PR #1 (https://github.com/marshallhouston/tools/pull/1). Testing-related findings are intentionally out of scope per user direction — this is personal tooling, no tests.

Source of findings: `.context/compound-engineering/ce-review/20260417-034229-3494576f/` (per-reviewer JSON + diff.patch).

All tasks target `plugins/obsidian-weaver/scripts/connect-sync.py` unless noted. Execute groups in order — group A fixes are load-bearing for B/C/D verification.

---

## Group A — Atomicity core (P0)

### A1. Replace `acquire_lock` with `O_EXCL` atomic lock

**File:** `connect-sync.py:~55-68`
**Bug:** `os.path.exists()` then `open(..., 'w')` is TOCTOU — two concurrent runs both pass the check and both take the lock.
**Fix:** Use `os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)`. On `FileExistsError`, read the existing lock, check `mtime` against `LOCK_TTL`; if stale, `os.unlink` and retry once; otherwise emit structured JSON error `{"status":"error","reason":"sync in progress"}` and exit 1.
**Verify:**
1. `python3 connect-sync.py &` in one terminal, immediately run `python3 connect-sync.py` in another. Second must exit 1 with the structured error, not proceed.
2. Manually `touch -t 200001010000 $VAULT/_connections/.sync.lock` then run — script must detect stale lock, unlink, acquire.

### A2. Atomic writes everywhere via `tempfile + os.replace`

**File:** `connect-sync.py:~106 (save_state)`, `~236 (update_connection_page)`, `~300 (inject_backlinks)`, `~558 (rebuild_index)`
**Bug:** All writes are `open(p, 'w')` which truncates in-place. SIGKILL, ENOSPC, or iCloud/Dropbox sync-conflict mid-write leaves torn files. `.registry.json` is hand-curated with no backup.
**Fix:** Add a single helper at module scope:
```python
def atomic_write(path: str, data: str) -> None:
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        raise
```
Route all 4 write sites through it. Tempfile must be a same-dir sibling (not `/tmp`) so `os.replace` stays on one filesystem.
**Verify:**
1. `strace`/`dtruss` on one sync run and confirm every markdown/json write goes through a temp path + rename.
2. Run sync, SIGKILL mid-run (`kill -9` during a large `--since 2020-01-01` scan). Relaunch — no file should be empty or truncated; state file either has the old content or the new, never torn.

### A3. Handle `JSONDecodeError` in `load_state` and `load_registry`

**File:** `connect-sync.py:~94` (`load_registry`), `~105` (`load_state`)
**Bug:** A torn JSON file from a prior crash (before A2 lands, or if a user hand-edits badly) raises uncaught `json.JSONDecodeError` — every subsequent run crashes until the user manually deletes the file.
**Fix:**
- `load_state`: on `JSONDecodeError`, log warning to stderr, return `{"last_sync": None}` so the next run proceeds with a full rescan.
- `load_registry`: on `JSONDecodeError`, emit structured JSON error identical in shape to the registry-missing error added in b265e5c (include parse line/column + pointer to `_connections-seed/README.md`) and exit 1.
**Verify:**
1. `echo '{broken' > $VAULT/_connections/.registry.json` then run — must exit with JSON error, not traceback.
2. `echo '{broken' > $VAULT/.obsidian-sync-state.json` (or wherever STATE lives) then run — must proceed, rescan from start, print warning.

---

## Group B — First-run UX (P1)

### B1. Fail fast when `OBSIDIAN_VAULT` is unset

**File:** `connect-sync.py:~34`
**Bug:** Defaults to `~/Documents/vault` silently. Script returns `no_changes` against the phantom path — agent and user can't distinguish "healthy" from "misconfigured".
**Fix:** If `os.environ.get("OBSIDIAN_VAULT")` is empty/unset, emit `{"status":"error","reason":"OBSIDIAN_VAULT not set","hint":"run /obsidian-setup"}` and exit 1. Same treatment if the path doesn't exist on disk.
**Verify:**
1. `unset OBSIDIAN_VAULT; python3 connect-sync.py` — must exit 1 with structured error pointing at `/obsidian-setup`.
2. `OBSIDIAN_VAULT=/nonexistent/path python3 connect-sync.py` — must exit 1 with `reason:"vault not found"`.

### B2. Persist vault path across Claude Code bash calls

**File:** `plugins/obsidian-weaver/skills/obsidian-setup/SKILL.md` + `connect-sync.py` + other skills as needed
**Bug:** `export OBSIDIAN_VAULT=...` in a Bash tool call does not persist to the next Bash tool call — each invocation is a fresh shell. `/obsidian-setup` appears to work but `/today` in the same session re-fails with "vault not set".
**Fix:**
- `/obsidian-setup` writes the vault path to `~/.obsidian-weaver/config` (single line, absolute path).
- `connect-sync.py` (and skills that need it) read `OBSIDIAN_VAULT` first, then fall back to `~/.obsidian-weaver/config`, then fail (B1).
- `/obsidian-setup` also prints a note telling the user to add `export OBSIDIAN_VAULT=...` to their shell rc for CLI use outside Claude Code.
**Verify:**
1. Fresh Claude Code session, `unset OBSIDIAN_VAULT`, run `/obsidian-setup`. Immediately run `/today` in the same session — must succeed, not re-prompt for vault path.
2. `cat ~/.obsidian-weaver/config` — shows the absolute vault path.

---

## Group C — Correctness bugs in the write path (P1)

### C1. Fix `note_name_from_path` — use `splitext`, not `replace`

**File:** `connect-sync.py:~190`
**Bug:** `rel.replace('.md', '')` strips every occurrence. `release.md-notes.md` → `release-notes`, then `[[release-notes]]` won't match its own file.
**Fix:** `name, _ = os.path.splitext(rel); return name.replace(os.sep, '/')`.
**Verify:** Unit-style: `python3 -c "from connect_sync import note_name_from_path; print(note_name_from_path('release.md-notes.md'))"` → `release.md-notes`.

### C2. Fix trailing-newline crash in year-header splice

**File:** `connect-sync.py:~228` (inside `update_connection_page`, the `content.index('\n', idx)` call after finding the year header)
**Bug:** Raises `ValueError` when the matched header is the final line with no trailing newline. Kills sync after prior writes committed; `last_sync` never advances, same files re-scanned every run.
**Fix:** Use `content.find('\n', idx)`; if it returns `-1`, treat the insertion point as `len(content)` and ensure content ends with `\n` before splicing.
**Verify:** Create a connection page whose final line is the year header (`echo -n '## 2026' >> $VAULT/_connections/.../Foo.md`). Run sync with a new mention — must insert under the year header, not crash.

### C3. Anchor `inject_backlinks` to unique marker only

**File:** `connect-sync.py:~277-300`
**Bug:** `rfind('## Connections')` walks past the auto-marker. If a user ever authored their own `## Connections` section anywhere above the marker, next sync destroys it and replaces it with the auto-generated block.
**Fix:** Replace `rfind` logic with: find the `<!-- obsidian-weaver:backlinks -->` marker only; if absent, append a new block. Never hunt for `## Connections` by heading text. Also reject (no-op with warning) if any `## ` header appears between the marker and the next `## ` boundary that doesn't match the auto-heading — indicates user edited the auto-block and we'd be overwriting their changes.
**Verify:**
1. Create a note with a user-authored `## Connections` containing `- manual note` at the top. Run sync. User section must be preserved; auto-section appended below marker.
2. Run sync twice in a row on the same note — second run is a no-op (idempotent, diff-clean).

---

## Group D — Path containment hardening (P0 / P1)

### D1. Tighten `safe_connection_filename` to allowlist regex

**File:** `connect-sync.py:~79-81`
**Bug:** Current denylist strips only `/:?"`. Deep-mode LLM can be prompt-injected via captured note content into writing `canonical: "../../../../Users/marshall/.ssh/authorized_keys"`. Since it only contains `/` (removed), the result is a path-traversal string that `os.path.join` happily escapes `_connections/` with, then `inject_backlinks` opens in `'w'`.
**Fix:** Allowlist: `re.sub(r'[^A-Za-z0-9 _\-\.]', '-', name)`. Then `.strip('. ')` to kill leading/trailing dots and whitespace. Reject (raise) if result is empty, `.`, `..`, or a Windows reserved name (`CON`, `PRN`, `AUX`, `NUL`, `COM[1-9]`, `LPT[1-9]`).
**Verify:**
1. `python3 -c "from connect_sync import safe_connection_filename as f; print(f('../../etc/passwd'))"` → must produce a plain filename, no `..`.
2. `f('')`, `f('.')`, `f('CON')` all raise.

### D2. `realpath`-containment check for write paths

**File:** `connect-sync.py` — all sites that compute a write path: `update_connection_page`, `inject_backlinks`, `rebuild_index`, and the `--file <path>` CLI arg.
**Bug:** `--file` accepts any absolute path; a rogue invocation can rewrite files outside the vault. Even with D1 in place, defense-in-depth `realpath` check catches future regressions.
**Fix:** Add helper:
```python
def assert_inside_vault(p: str) -> None:
    rp = os.path.realpath(p)
    rv = os.path.realpath(VAULT)
    if not (rp == rv or rp.startswith(rv + os.sep)):
        raise ValueError(f"path escapes vault: {p}")
```
Call before every write, and before accepting `--file`.
**Verify:**
1. `python3 connect-sync.py --file /etc/passwd` — must exit with `path escapes vault` error, not write.
2. Symlinked vault test: `ln -s /tmp/real-vault ~/linked-vault; OBSIDIAN_VAULT=~/linked-vault python3 connect-sync.py` — must succeed (realpath resolves both sides).

---

## Group E — Resilience (P1 / P2)

### E1. Per-file try/except in main loop

**File:** `connect-sync.py:~353-390`
**Bug:** One failing file aborts the whole batch; earlier connection pages updated, later backlinks missing — inconsistent state with no resume semantics.
**Fix:** Wrap each file's processing block in try/except; on failure, append `{path, error}` to a `failures` list, continue. At end, include failures in the JSON summary. Do not advance `last_sync` past a failed file (ensures retry on next run).
**Verify:**
1. `chmod 000` one note, run sync — must process other files, surface the failure in the JSON summary, exit 0 with non-empty `failures`.
2. Next run must reprocess the previously-failed file (after `chmod 644`).

### E2. Top-level try/except in `_run_sync` emitting structured JSON

**File:** `connect-sync.py` (wrap the main function body)
**Bug:** Misuse of `--since`, bad argv, unreadable registry produce Python tracebacks. Agent can't programmatically recover.
**Fix:** Wrap the entire `_run_sync` body in try/except; on any uncaught exception, emit `{"status":"error","reason": type(e).__name__, "message": str(e)}` to stdout and exit 1.
**Verify:**
1. `python3 connect-sync.py --since nonsense-date` — structured JSON error, no traceback.
2. `python3 connect-sync.py --file` (no value) — structured JSON error, no traceback.

### E3. Surface skipped files in JSON output

**File:** `connect-sync.py:~300` (`scan_file`) and similar silent-swallow sites
**Bug:** `PermissionError` / `UnicodeDecodeError` silently skip files — user has no signal.
**Fix:** Collect skipped paths with reason into a `skipped` list; include in JSON summary.
**Verify:** Create a UTF-16-encoded `.md` file in the vault; run sync — must appear in the `skipped` section of output JSON.

---

## Group F — Documentation & consistency (P2)

### F1. Unify fallback policy when Paths table is missing

**Files:** `plugins/obsidian-weaver/skills/capture/SKILL.md:~98`, `plugins/obsidian-weaver/skills/connect-sync/SKILL.md` Step 4, `plugins/obsidian-weaver/skills/today/SKILL.md`
**Bug:** `/today` hard-fails without the Paths table; `/capture` and `/connect-sync` silently fall back to hardcoded folders. Inconsistent.
**Fix:** Align all three on "hard-require `/obsidian-setup`" (matches frozen decision that Paths table is runtime source of truth). Remove fallback paragraphs from capture Step 7 and connect-sync Step 4.
**Verify:** Delete a local `CLAUDE.md` Paths row temporarily; invoke each of `/today`, `/capture`, `/connect-sync` — all three must refuse identically with "run `/obsidian-setup` first".

### F2. README contradicts itself on relocating `_connections/`

**File:** `plugins/obsidian-weaver/README.md:~118` vs `:~160-161`
**Bug:** Line 118 says edit `CONNECTIONS` in the script. Lines 160-161 say export `OBSIDIAN_CONNECTIONS`. Pick one.
**Fix:** Delete the "edit the script" guidance (line 118 block). Keep only the env-var path.
**Verify:** `grep -n "edit.*CONNECTIONS" plugins/obsidian-weaver/README.md` returns nothing.

### F3. Trim `CLAUDE.md.template` obsidian CLI surface

**File:** `plugins/obsidian-weaver/templates/CLAUDE.md.template:~119`
**Bug:** Lists `obsidian links / backlinks / rename / tags` commands that no skill or script actually calls — drift risk.
**Fix:** Remove the unused commands from the template's obsidian-CLI section. Keep only what skills actually invoke (search, create, append, read — whatever is actually used; audit by grep).
**Verify:** For each remaining command in the template, `grep -r "obsidian <cmd>" plugins/obsidian-weaver/` shows at least one real caller.

---

## Group G — Skill trigger descriptions (P3)

### G1. Expand `/capture` trigger verbs

**File:** `plugins/obsidian-weaver/skills/capture/SKILL.md` frontmatter `description`
**Bug:** Lists `save`/`capture`/`dump` but not `log this thought`, `jot down`, `note down`, `stash this`, `remember this`, `file this` — user's own examples miss.
**Fix:** Extend the description verb list.
**Verify:** Fresh Claude session, say "log this thought: X". Skill must fire. Repeat for each new verb.

### G2. Broaden `/today` to status-query phrasings

**File:** `plugins/obsidian-weaver/skills/today/SKILL.md` description
**Bug:** Framed as note-creator only. "what's on my plate today", "what do I have going on" won't route.
**Fix:** Add status-query phrasings to the description.
**Verify:** Fresh Claude session, "what's on my plate today" — must fire `/today`.

### G3. Add `weave`/`crosslink`/`rebuild` to `/connect-sync`

**File:** `plugins/obsidian-weaver/skills/connect-sync/SKILL.md` description
**Bug:** Plugin is `obsidian-weaver` but description omits `weave`. Also missing `crosslink`, `link my notes`, `rebuild the graph`.
**Fix:** Extend verb list.
**Verify:** Fresh session: "weave my notes" → `/connect-sync` fires.

---

## Deferred (not this session)

These are architectural or refactor findings that should become separate follow-ups, not part of the fix PR:

- **#13** Single-source-of-truth decision for connections path (env var vs Paths table) — architectural.
- **#12** Lock heartbeat for long first-run syncs that exceed 120s TTL.
- **#18** Migrate argv parsing to `argparse`.
- **#19** Add type hints across the module.
- **#22** Skill-trigger overreach gating (requires design for confirmation flow).
- **#15** Cache `scan_file` result to avoid double scan.
- **#24 / #25** Derive `SKIP_DIRS` from Paths table; replace module-level globals with a `Config` object.

---

## Execution order

1. Group A (atomicity core) — lands as one commit.
2. Group B (first-run UX) — one commit.
3. Group C (write-path correctness) — one commit.
4. Group D (path hardening) — one commit.
5. Group E (resilience) — one commit.
6. Group F (docs consistency) — one commit.
7. Group G (trigger descriptions) — one commit.

Seven commits on the existing `worktree-obsidian-starter` branch, then `git push` to update PR #1.

Verification after each group: run `python3 plugins/obsidian-weaver/scripts/connect-sync.py` against a scratch vault and confirm the verification steps for every task in the group pass. No automated test suite — all checks are manual observation.
