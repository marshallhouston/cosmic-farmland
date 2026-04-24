---
name: systematize
description: "Promote a lesson from passive memory to active enforcement. Use when the user says /systematize, 'systematize this', 'memory is fallible', 'make this stick', 'turn this into a rule', or after any correction/learning that needs to survive session turnover. Picks the highest viable enforcement tier (hook > CI gate > script > doc > memory) and ships the artifact."
argument-hint: "[lesson description] -- e.g. '/systematize never commit seed files without URL verification'"
---

# /systematize -- Promote lessons from memory to enforcement

Memory is tier 4 of enforcement: passive, session-scoped, lossy. Lessons worth remembering are lessons worth gating. This skill picks the highest viable tier and ships the artifact so the lesson survives session turnover, contributor turnover, and marshall's own forgetting.

## When to use

- `/systematize <lesson>`
- "memory is fallible"
- "how do we make this stick"
- "turn this into a rule"
- "systematize this"
- After any correction the user expects to apply every time
- After any learning that emerged from a real incident (postmortem, close call, wasted hours)
- When the user is writing the same memory note for the third time

## The tier hierarchy

Rank enforcement from most durable to least:

| Tier | What | When | Survives |
|------|------|------|----------|
| **1: Hook** | Pre-tool / pre-commit / pre-prompt hook that blocks the wrong action at the moment of attempt | Rules that can be mechanically detected and have a clear "stop" semantic | Session, contributor, agent, process turnover |
| **2: CI gate** | Workflow job that blocks PR merge on violation | Rules that need codebase-wide enforcement, not just author's machine | Contributor + session turnover |
| **3: Script / test** | Repo-committed script or test the author runs before commit | Rules the author can run but might skip | Session turnover, not contributor turnover |
| **4: Doc (CLAUDE.md / AGENTS.md / README)** | Documented convention read by humans + agents | Light conventions with context that can't be mechanized | Session turnover if read; useless if skimmed |
| **5: Memory** | Claude-local session memory | Preferences, context, user-specific taste | Nothing; lossy and session-scoped |

Every lesson starts at tier 5. Promote until you hit the highest viable tier, stop, ship.

## How to run

### Step 1: State the lesson

One sentence. "Never do X because Y." "Always do X when Y." If marshall gave you the lesson in the invocation, repeat it back. If not, ask: "What's the rule?"

Examples:
- "Never commit sermon seed files without verifying sourceUrls resolve."
- "Don't push directly to main; always go through a PR."
- "When writing tests, include a `// Bug:` / `// Contract:` / `// Refactor:` justification."
- "Never use em-dashes in user-facing text."

### Step 2: Classify the lesson

Walk the decision tree top-down. First matching tier wins.

**Tier 1 (Hook) is viable if:**
- The violation is detectable by static inspection of the tool call / prompt / diff
- There's a clear "should I block this?" yes/no answer
- The fix is pointable (file + change) rather than judgment-requiring
- Example triggers: "always", "never", "before any", "after every"
- Concrete artifact: `hookify` rule, PreToolUse hook, pre-commit hook

**Tier 2 (CI gate) is viable if:**
- Tier 1 doesn't fit (rule needs more than local context, or needs to run in a reproducible env)
- The check is scripted / automated
- Blocking merge is the right enforcement point
- Concrete artifact: `.github/workflows/*.yml` job, usually wrapping a repo script

**Tier 3 (Script / test) is viable if:**
- Tier 1 + 2 don't fit (author-driven, not automation-driven)
- There's a script or test that makes the check cheap to run
- Example: a Bun / shell / test file in `scripts/` or `__tests__/`
- Concrete artifact: committed script + a `package.json` entry + a docs ref

**Tier 4 (Doc) is viable if:**
- Tier 1-3 don't fit (rule needs human judgment)
- The rule has enough context that a 1-paragraph doc note actually helps
- Concrete artifact: section in CLAUDE.md / AGENTS.md / README / a narrow skill

**Tier 5 (Memory) is only the right answer if:**
- The rule is user-taste / user-context, not a codebase rule
- Or the rule is too vague to mechanize and too narrow to document
- Or the lesson is tentative and you're still deciding if it's real
- If you land here, explicitly name it: "This stays at tier 5 because X"

### Step 3: Ship the highest viable artifact

Build the actual file. Don't just describe it. Patterns:

**Tier 1 -- hookify rule (user-local):**
```
~/.claude/hookify/<slug>.yml
```
Uses `hookify:writing-rules` skill. Pattern: match a regex in the tool call args or file diff, return block-with-message when matched.

**Tier 1 -- pre-commit hook (repo-local):**
```
.husky/pre-commit or similar
```
Add a shell one-liner that runs the relevant script with `--staged` or `--added-only`.

**Tier 2 -- CI gate:**
```
.github/workflows/<name>.yml
```
Hang a new job off the existing CI workflow, or add a job to `ci.yml`. Gate it on `paths-filter` or an explicit `git diff --name-only` check so it only runs on relevant PRs.

**Tier 3 -- script:**
```
scripts/<name>.{sh,ts}
package.json: "<slug>": "bun scripts/<name>.ts"
```
Write a standalone runnable script. Commit it.

**Tier 4 -- doc:**
```
CLAUDE.md or AGENTS.md
```
Add a short section with the rule + one example + one common failure mode. Under a heading future sessions will scan for.

**Tier 5 -- memory:**
```
~/.claude/projects/<slug>/memory/<file>.md
```
Plus an entry in MEMORY.md. Only do this if the prior tiers genuinely don't fit.

### Step 4: Cross-link the artifact back to memory

Even when you ship tier 1-4, update the user's memory to point at the artifact. This prevents re-relitigation. Format:

```markdown
- [Rule title](file.md) -- summary. Enforced in-repo at <path>. See <docs ref>.
```

This way next session you'll read memory, see the pointer, and NOT recreate the gate or second-guess it.

### Step 5: Report

Tight summary:

```
Systematized: <lesson>
Tier chosen: <N> <reason-tier-was-picked>
Artifact: <path>
Cross-ref: <memory or doc ref updated>
Still-TODO (if any): <e.g. tier 1 hook not built because hookify plugin missing>
```

Done. No followups, no "want me to also..." questions unless a genuinely load-bearing piece is blocked.

## Anti-patterns to avoid

- **Don't stop at tier 5 without declaring it intentional.** If you save a memory note and don't even consider promotion, you've done the weak version.
- **Don't build tier 1 for rules that need judgment.** A hook that blocks everything with "warning" in it is noise. Classify carefully.
- **Don't skip cross-linking.** A gate without a memory pointer means next session still re-derives the manual workflow.
- **Don't build N+1 artifacts when N is enough.** If tier 2 covers the rule, don't also build tier 3. Each artifact is maintenance weight.
- **Don't treat every preference as a rule.** "User likes terse responses" is tier 5. "Never push to main" is tier 1 or 2.

## Example session

User: `/systematize never commit sermon seed files without verifying sourceUrls resolve`

Agent:
1. State lesson: "Never commit sermon seed files where an added sourceUrl returns 4xx/5xx."
2. Classify:
   - Tier 1 viable? Yes-ish (pre-commit hook could run verifier with --added-only) but requires husky + lives in user's machine only.
   - Tier 2 viable? Yes. CI job can run on any PR touching seed files.
   - Pick tier 2 as floor, offer tier 1 pre-commit hook as optional add.
3. Build:
   - `scripts/verify-sermon-urls.ts` (tier 3 dep)
   - `package.json` script entries (tier 3)
   - `.github/workflows/ci.yml` new job (tier 2)
   - `CLAUDE.md` "Sermon Seed Curation" section (tier 4 cross-ref)
4. Cross-link: update memory MEMORY.md index entry to point at CLAUDE.md section + PR number.
5. Report: "Tier 2 CI gate shipped. Tier 1 pre-commit hook optional; run `/systematize tier-1-upgrade <lesson>` to add."

## Tone

Terse. Structural. This skill exists because the user is tired of saying "memory is fallible" -- so the default attitude is "pick a real tier and ship the artifact." Don't moralize about memory; just promote.
