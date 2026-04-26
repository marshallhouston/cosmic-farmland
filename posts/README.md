# posts

source files for linkedin/instagram carousel decks. html + caption + per-deck `_base.css` copy.

pngs and pdfs are generated artifacts and live in `out/` (gitignored). regenerate with:

```
bash plugins/cosmic-farmland/skills/slideshow/scripts/build.sh posts/<deck-name>
```

## ship-classifier (primary)

5-slide deck reframing `/ship` as a 4-color ci classifier (green / yellow / blue / red) rather than a workflow automation. caption included.

slide voice notes:
- slide 1 hook: `/ship is a classifier, not a button.`
- slide 2 taxonomy: green=pass, yellow=flake (re-run once), blue=cosmetic non-required, red=blocker
- slide 3 gates: real `gh pr view` commands from ship.md
- slide 4 quote: `a failing check is a signal, not a dead-end.`
- slide 5 closer: `build the classifier. trust the classifier.` + repo url

## alts/

three drafts that didn't lead with the system. kept for cannibalization, not posting:

- `why-i-built-ship/` -- 7 slides, more origin-story framing (caption included)
- `bike-shed/` -- 5 slides, `refreshing the pr tab is not work`
- `three-prs/` -- 5 slides, `three prs shipped. zero tabs refreshed.`

each has voice issues flagged during review (linkedin-coach surface, listicle drumroll, generic ctas). the ship-classifier deck supersedes them.

## voice rules

before editing any slide, re-read `plugins/cosmic-farmland/skills/slideshow/VOICE.md`. mechanical checks live in `plugins/cosmic-farmland/skills/slideshow/scripts/check.sh`.
