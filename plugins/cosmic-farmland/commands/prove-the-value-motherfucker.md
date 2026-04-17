---
description: Prove The Value Motherfucker audit. Alias for /fart-smell-detection. Levels whiff|sniff|huff|dutch-oven-yourselff.
argument-hint: "[whiff|sniff|huff|dutch-oven-yourselff] [PR #N | git-range | --staged]"
---

Invoke the `fart-smell-detection` skill.

Args: `$ARGUMENTS`

Parse args:
- First token matching `whiff|sniff|huff|dutch-oven-yourselff` → level. Default `sniff`.
- Remaining tokens → target (PR number, git range, or `--staged`). If absent, skill resolves per its input rules.

Follow the skill's audit process and output format exactly. Do not soften verdicts.
