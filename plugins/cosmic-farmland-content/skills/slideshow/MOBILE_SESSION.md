# Mobile session context

Source: claude.ai/code session `01BXTKSaXRYtBE93EvXkpkW8` (2026-04-23).
Pasted by marshall — not auto-fetched (claude.ai has no transcript API and the
isolated-Chrome scrape required a second login).

## Inspiration

Post from an 11x-style creator describing a LinkedIn slideshow skill:
- 3-slide minimum: hook / content / CTA
- HTML templates, reusable, brand-consistent
- Render to PDF for native LinkedIn carousel upload
- Skill layout: `SKILL.md` + `/templates/*.html`

Screenshots (not saved) showed 11x deck using classical brand chrome (Greek
temple, blackletter, cream) with content variants (`-bullets`, `-numbered`,
`-quote`) sharing the same chrome.

## Adaptation decided on mobile

Repo context: cosmic-farmland is a plugin collection, not a content shop →
content will skew dev/tooling, so the deck needs **code** and **terminal**
variants that 11x doesn't have.

Brand direction (placeholder until real assets land):
- pixel crop-rows dissolving into starfield
- serif/slab headline
- single phosphor accent (aurora teal or sodium orange) on deep indigo
- watermark once, reuse everywhere

## What shipped in commit 274f2f4

```
plugins/cosmic-farmland-content/skills/slideshow/
  SKILL.md
  templates/
    _base.css                       # all brand vars
    slide-01-hook.html
    slide-content-bullets.html
    slide-content-numbered.html
    slide-content-quote.html
    slide-content-code.html         # added vs 11x
    slide-content-terminal.html     # added vs 11x
    slide-content-stat.html
    slide-last-cta.html
    caption.txt
  scripts/build.sh                  # headless-Chrome → PNGs + PDF
  assets/README.md
  commands/slideshow.md
```

Build script validated syntactically only — sandbox had no Chrome, no real
render performed.

## Next steps (from mobile hand-off)

1. Drop real `logo.svg` (+ optional `watermark.png`) into `assets/`.
2. Edit `:root` in `templates/_base.css`: swap colors, font stacks, flip
   `--brand-watermark-url` from `none` to the file path.
3. Global find/replace: `<div class="brand-logo-fallback">cosmic-farmland</div>`
   → `<div class="brand-logo"></div>` across all templates.
4. Run `/slideshow <topic>` end-to-end on something real; iterate CSS from
   the rendered output, not the HTML source.
