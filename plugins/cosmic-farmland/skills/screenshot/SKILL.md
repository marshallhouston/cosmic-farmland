---
name: screenshot
description: "Read user's newest screenshot(s) from their screenshot folder and execute the intent they give. Trigger: /screenshot, /screenshot N, /screenshot <intent>, /screenshot N <intent>."
argument-hint: "[count] [intent...]  e.g. '/screenshot', '/screenshot fix', '/screenshot 4 make infographic'"
---

## Resolve folder

```bash
DIR="${SCREENSHOT_DIR:-$(defaults read com.apple.screencapture location 2>/dev/null)}"
DIR="${DIR:-$HOME/Desktop}"
DIR="${DIR/#\~/$HOME}"
```

Folder missing or no `*.png` inside: tell user, suggest `export SCREENSHOT_DIR=...`. Don't fabricate.

## Parse args

- No args: count=1, intent="explain"
- First token integer: count=N (cap 10), rest = intent
- First token non-numeric: count=1, all tokens = intent

## Get newest N

```bash
ls -t "$DIR"/*.png 2>/dev/null | head -N
```

macOS screenshot filenames contain a narrow no-break space (U+202F) before AM/PM. Direct quoting (`rm "..."`) breaks. For any subsequent file op (delete, move, convert), pipe through xargs -0:

```bash
ls -t "$DIR"/*.png | head -1 | tr '\n' '\0' | xargs -0 <cmd>
```

## Read + act

`Read` each abs path (multimodal, no copy). `Read` handles the special chars fine. Then read images + intent together.

| Intent | Action |
|---|---|
| (empty), `explain`, `huh`, `wtf` | Describe what's in the image. Surface what's interesting or non-obvious. |
| `fix` | Image shows an error or broken UI. Find the bug in the current repo, edit code. |
| `do this`, `remix`, `like this` | Image shows a pattern. Apply it to user's current work, remixed for their goals. |
| `make X`, `turn into X` | Produce X from image content. |
| anything else | Infer from text + image together. |
