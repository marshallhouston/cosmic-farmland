---
name: slideshow
description: "LinkedIn/IG carousel from topic/outline. HTML slides + PNGs + PDF + caption. Triggers: 'slideshow', 'carousel', 'make slides', 'deck for LinkedIn'."
---

# Slideshow -- On-brand Carousel Builder

Turn a topic or rough outline into a LinkedIn/Instagram-sized carousel (1080x1350) using the cosmic-farmland brand templates. Output is a folder containing numbered HTML slides, PNG exports, a combined PDF, and a draft caption ready to paste into LinkedIn.

## When to use

- "make a slideshow / carousel about X"
- "turn this release note / lesson / thread into a LinkedIn post"
- "pack this into slides with our brand"
- Any time the user wants visual social content from written material.

## Inputs you need

Before building, make sure you have:
1. **Topic / angle** -- one sentence. If the user gave a whole outline, the angle is the headline.
2. **Audience** -- who this is for (devs using Claude Code? founders? ops people?). Shapes tone.
3. **Source material** -- an outline, a doc, a PR, a thread, a conversation excerpt. If none, ask.
4. **CTA** -- what the last slide should drive (follow, DM, link, reply). Default: "Follow for more" if not specified.

If any of these are missing and can't be inferred, ask once, then proceed.

## The slide structure (mirrors the 11x pattern)

Every carousel has three slots:

1. **Hook slide** (slide 01) -- `slide-01-hook.html`. Kicker + big headline. One idea. No body.
2. **Content slides** (slides 02 through N-1) -- pick from the content template catalog below. 3-6 content slides is the sweet spot. Each slide is one idea.
3. **CTA slide** (last slide) -- `slide-last-cta.html`. Closing line + next action.

Total length: 5-8 slides. Longer loses retention.

## Template catalog

All templates live in `templates/`. Each is a standalone HTML file sized 1080x1350. Copy the template to the output dir, rename with a zero-padded slide number, fill the slots.

| Template | Use when |
|---|---|
| `slide-01-hook.html` | Slide 1. Kicker (3-word category) + headline (the hook). |
| `slide-content-bullets.html` | 3-5 short bullets. Default for "what you get / what to do" slides. |
| `slide-content-numbered.html` | Ordered steps, rankings, a top-N list. |
| `slide-content-quote.html` | A pull-quote, a strong line, a customer/user voice. One sentence max. |
| `slide-content-code.html` | A code snippet (<=12 lines). Use for command demos, API calls, config. |
| `slide-content-terminal.html` | Terminal prompt + output. Use for CLI walkthroughs. |
| `slide-content-stat.html` | A single big number + label + support line. Use for "the real bill" style stat slides. |
| `slide-last-cta.html` | Last slide. Closing line + CTA + handle. |

Prefer variety across a deck -- don't stack 5 bullet slides in a row. Mix stat/quote/bullets/code to create rhythm.

**Size limits (avoid overflow):** bullets max 5, numbered steps max 5, code snippets max 12 lines (and max ~50 chars per line -- the code block clips horizontally, not wraps), terminal output max 10 lines. Beyond these, content will clip the 1350px canvas.

**Inline code in prose:** `<code>foo</code>` inside bullets, steps, or body text renders monospace with a subtle background pill. Useful for commands, flags, file paths in plain-English sentences. Keep to short fragments -- no `white-space: wrap`, so long code strings clip.

**Fonts:** `_base.css` references Iowan Old Style, Inter, and JetBrains Mono. These are available on macOS or degrade to Palatino/system-ui/Menlo fallbacks. On Linux/CI, install those fonts or ship webfonts in `assets/fonts/` + an `@font-face` block.

## Slot conventions

Each template uses `{{DOUBLE_BRACE}}` placeholders. When you fill a template, replace every placeholder. Do not leave empties -- if a slot is optional and unused, delete the surrounding element rather than leaving `{{KICKER}}` in the file.

Common slots:
- `{{KICKER}}` -- small uppercase label above the headline (e.g. "FEATURE 02", "COLD MATH")
- `{{HEADLINE}}` -- the main line on the slide
- `{{SUBHEAD}}` -- optional supporting line under the headline
- `{{BODY}}` / `{{BULLETS}}` / `{{STEPS}}` / `{{QUOTE}}` / `{{CODE}}` -- main content
- `{{ATTRIBUTION}}` -- quote byline
- `{{CTA}}` / `{{HANDLE}}` -- closing slide only

### Repeating slots

Bullets and numbered-step templates ship with a maximum set of rows (5 bullets,
3 steps). For fewer rows, **delete the extra `<li>` blocks**. For more steps,
duplicate the last `<li>` block before filling. Never leave a placeholder like
`{{BULLET_5}}` in the final HTML -- it will render literally.

### Code highlighting

`slide-content-code.html` renders plain text monochrome by default. To colorize,
hand-wrap tokens: `<span class="keyword">def</span>`, `<span class="string">"x"</span>`,
`<span class="comment"># ...</span>`. There is no auto-tokenizer.

## How to build a deck

1. **Plan the slides.** Write the slide list first as plain text -- slide number, template choice, one-line content summary. Get approval from the user if they gave you latitude, or proceed directly if they gave you a concrete outline.
2. **Pick the output dir.** Default: `./out/slideshow-<slug>/` in the current repo (where `<slug>` is a kebab-case summary of the topic). Create it.
3. **Copy + fill templates.** For each slide, copy the chosen template from the skill dir (`${CLAUDE_PLUGIN_ROOT}/skills/slideshow/templates/<template>.html`) into the output dir as `slide-01.html`, `slide-02.html`, etc. Fill every placeholder. Keep copy tight -- carousel slides punish long text.
4. **Copy the shared stylesheet.** Copy `templates/_base.css` into the output dir so the slides render without the skill dir present.
5. **Draft the caption.** Copy `templates/caption.txt` into the output dir as `caption.txt`, fill it in. LinkedIn caption = hook + 2-4 short paragraphs + CTA + link (optional). Keep it under 1300 chars to avoid the "see more" cut-off on mobile -- or write for the cut intentionally.
6. **Build the outputs.** Run the build script:
   ```bash
   "${CLAUDE_PLUGIN_ROOT}/skills/slideshow/scripts/build.sh" <output-dir>
   ```
   Produces `slide-NN.png` for each slide (2160x2700, DPR=2 for crisp zoom) and a single combined `slideshow.pdf` (PDF page geometry stays 1080x1350 px). Override DPR with `SLIDESHOW_DPR=1` (or 3) if needed.

   The build runs `scripts/check.sh` first and aborts on voice violations (em-dashes, fake attributions, invented precision, coach register, Title-Case headings). Fix the copy rather than bypassing. Set `SLIDESHOW_SKIP_CHECK=1` only with a real reason.
7. **Report.** List what you produced, with absolute paths. Tell the user the PDF is what they upload to LinkedIn (LinkedIn renders PDFs as swipeable carousels). Tell them where the caption is.

## Copywriting rules

**Before writing any slide, read `VOICE.md` in this same directory.** It is the
authoritative guide to marshall's voice (derived from `~/code/marshallhouston.wtf/CLAUDE.md`
and the hookify rules on his site). It overrides anything below if they conflict.

Highlights from `VOICE.md` (not a substitute for reading it):

- **Lowercase everything** in the HTML source. Kickers render all-caps visually
  via CSS; the content is still lowercase. Proper nouns keep their caps.
- **No em-dashes (`--` dash dash or rephrase).** No en-dashes. Hard rule.
- **First person, lowercase `i`.** `i built /ship`, not `I built /ship`.
- **One idea per slide.** If a slide has two ideas, split it.
- **Headlines are statements, not teasers.** `an sdr costs you $11k/month`
  beats `you won't believe what sdrs cost`.
- **Numbers earn attention.** Prefer concrete figures over adjectives.
- **Cut adjectives ruthlessly.** `great / powerful / amazing` adds nothing.
- **Show the artifact.** Real commands, real commit hashes, real terminal
  output. Do not paraphrase an artifact when you can paste it.
- **Last slide is the close, not a recap.** Don't restate the hook.
- **If it could have been written by any AI, rewrite it.**
- **If it sounds like a LinkedIn post, burn it down.** Exception: `2026-04-22-unpromptable-linkedin-flip.md`
  is explicit satire and is *not* a style to imitate.

## Brand

Brand styling lives in `templates/_base.css` via CSS variables. When brand assets arrive, update the variables and drop files into `assets/`:

- `--brand-accent` -- accent color (headlines, rules, pull-quote marks)
- `--brand-ink` -- body text color
- `--brand-bg` -- slide background color
- `--brand-logo-url` -- small logo, top-left of every slide
- `--brand-watermark-url` -- decorative bottom watermark (optional)
- `--brand-font-display` -- display/heading font family
- `--brand-font-body` -- body font family
- `--brand-font-mono` -- code/terminal font family

Until real assets land, defaults produce a neutral-but-credible look so you can iterate on copy.

## Anti-patterns

- **Don't invent stats or quotes.** If the source material doesn't have it, don't put it on a slide.
- **Don't ship without building.** The HTML is not the deliverable -- the PDF is. Always run `build.sh`.
- **Don't skip the caption.** A carousel without a caption is a wasted post.
- **Don't fill `{{BRACES}}` with lorem ipsum.** If you don't have real content for a slot, delete the slot or cut the slide.
- **Don't freestyle the HTML structure.** Copy the template, fill the slots. If you need a layout the catalog doesn't have, add a new template rather than one-offing it inline.
