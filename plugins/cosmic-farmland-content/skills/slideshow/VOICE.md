# voice

the slideshow skill defaults to linkedin-influencer rhythm (hook stack, teaser
headlines, "3 things that changed everything"). that is not marshall's voice.
this file codifies what to write instead. the authoritative source is
`~/code/marshallhouston.wtf/CLAUDE.md`, the voice section of his own site. if
this file drifts from that, the site wins.

the slideshow `SKILL.md` references this file under "copywriting rules."
before filling any template, read this and filter every line through it.

## who we are writing as

solo dev who ships claude code plugins and shell scripts. exploratory, not
conclusive. ship the thinking, not the polished conclusion. bias to action
(bff: build, friction, fix). shares work because it might plant a seed, not
because an algorithm demanded three posts a week.

marshall has one post titled "3 songs, 1 uncomfortable truth" at
`/unpromptable/`. it is explicit satire, tagged `#LinkedInInfluencerInRecovery`.
the hookify rules on his site *exempt* that post from the lowercase hook so
it can mock the register. **never imitate that post's style in a real deck.**
if a line in the slideshow sounds like it came from that post, burn it down.

## hard rules (non-negotiable)

these mirror the hookify rules on the site. they block file writes over there.
here they govern what makes it onto a slide.

1. **lowercase everything.** titles, headings, kickers, body, cta. the kicker
   may render visually as all-caps (that is css `text-transform`), but the
   html content is lowercase. proper nouns keep their caps: `GitHub`, `LinkedIn`,
   `Claude Code`, names, places, acronyms. "ALL CAPS" for energy is fine
   (that is voice). "Title Case On A Slide" is not.
2. **no em-dashes (`—`) or en-dashes (`–`).** use a period, a comma, or two
   hyphens (`--`). if a sentence needs a dash to breathe, rewrite it shorter.
3. **first person singular.** `i`, `me`, `my`. lowercase `i` in body copy.
   not `I built /ship`, but `i built /ship`.
4. **fragments ok. periods doing structural work.** do not glue fragments
   into complex sentences for formality.
5. **if it could have been written by any ai, rewrite it.** generic
   competence is the tell. specificity is the counter.
6. **show the thing.** directory trees, code blocks, commit hashes, actual
   commands, real terminal output. do not paraphrase an artifact when you
   can paste it.

## keep

- **terse.** fragment > sentence when a fragment carries it. `ship first. fix
  the system after.` not `i've learned that it's important to ship and then
  iterate.`
- **specific over abstract.** name the file, the flag, the command. `gh pr
  merge --squash --delete-branch` beats "automate your merge workflow."
- **cross-domain references.** literary, philosophical, scientific, musical.
  a reference is a feature, not a reach. `hunter s. thompson`, `fleetwood
  mac`, `fear and loathing` all live in marshall's vocabulary.
- **self-deprecating warnings.** the cosmic-farmland readme opens with
  `this isn't ready for primetime and should not be relied on for stability`.
  that humility is the brand.
- **opinions with tradeoffs named.** `prefer the namespaced form unless
  muscle memory demands otherwise.` state the pick, then the exception.
- **name the feeling directly.** marshall's actual reaction, not a polished
  version. `having so, so much fun :)` is a real post ending.
- **plant the seed, don't prescribe.** `if this plants a seed for others,
  great; please take the ideas and run with them.` the reader is not a
  target. they are someone who might find it useful.
- **imperative to self, not to reader.** `just start. build something.
  literally anything.` that is marshall talking to himself out loud, not
  commanding you.

## kill

- **hook-stack openers.** `here's what nobody tells you about...` / `i used
  to [bad]. now i [good]. here's how.`
- **counterintuitive-truth framings.** `counterintuitive: the best way to
  ship faster is to slow down.` sounds deep, says nothing.
- **listicle drumroll.** `3 things that changed my workflow.` `5 lessons
  from shipping 100 prs.` the number is marketing, not content.
- **commanded ctas stacked for rhythm.** `follow. like. share.` the current
  deck's `steal the skill. post the first one this week.` drifts toward
  this. keep ctas to one concrete next step, not a drumbeat.
- **superlatives.** `insanely powerful`, `game-changing`, `the ultimate`. if
  the thing is good, the concrete fact will show it.
- **parables where the artifact would work.** do not explain ci with a chef
  metaphor when you can paste `gh pr checks --watch`.
- **guru posture.** no `i learned this from shipping at scale for 10 years`
  framing. the credential is the code.
- **second-person `you` stacking.** `you need to. you should. you will.`
  reads like a sales page. use `i` for the experience, describe the thing
  for the audience.
- **emoji as punctuation.** one deliberate emoji can land. three in a row
  are a tell.
- **"thought leadership" / "transformational" / "unlock your potential".**
  corporate voice. instant kill.

## headline patterns that work

- **statement of fact.** `i built /ship so i'd stop babysitting prs.`
- **concrete number + plain label.** `6 context switches per pr`
- **name the move, name the cost.** `trust ci. don't ask.`
- **artifact over abstract.** `pr #5, start to clean.` > `my pr-shipping
  workflow.`
- **quote the tool.** `a failing check is a signal, not a dead-end.` (real
  line from ship.md).

## headline patterns to kill

- `the surprising truth about ...`
- `here's what i wish i'd known ...`
- `why [specific x] is actually [counterintuitive y]`
- `[n] [plural thing]s that will [transform / change / 10x] your [noun]`
- questions the reader can't answer. `what if i told you ...`

## ctas

strong cta = one concrete next action the reader can take in under 60 seconds.

- `read ship.md: <url>`
- `steal the skill from cosmic-farmland`
- `reply with your version`

weak cta (avoid):

- `follow for more`
- `what's your take? let me know in the comments`
- `drop a ☕ if this helped`

if the post doesn't have a real next step, skip the cta slide. end on the
strongest content slide.

## captions

linkedin caption = setup + 2-4 short paragraphs + one real next action. write
it like you'd slack it to a smart friend who asked "what did you ship today?".
no warm-ups, no `so i've been thinking about...`, no `buckle up`.

- first line survives the mobile cutoff.
- paragraphs are 1-3 sentences. whitespace is the format.
- lowercase `i`. lowercase most things. proper nouns stay.
- no em-dashes.
- it is ok to end without a cta if the payoff is the story.

## quick test before build.sh

before running `build.sh`, re-read every slide and every caption line:

1. could a linkedin coach have written this? if yes, rewrite.
2. is there a concrete artifact (command, file, number, quote) on the
   slide? if not, add one or cut the slide.
3. does any heading or title have upper-case letters at the start of a
   word that is not a proper noun? if yes, lowercase it.
4. are there any em-dashes or en-dashes? if yes, replace with `.`, `,`,
   or `--`.
5. does the cta name a real action, or is it `follow for more`? if the
   latter, delete the slide.
6. does any line say `you` more than once? rewrite in first person or as
   a concrete description of the thing.
7. more than one adjective per slide? cut.

## anti-patterns caught in dogfood

these came up in real builds. `scripts/check.sh` blocks them at build time.
keep adding to this list as new ones surface.

- **fake-source attributions.** a pull-quote needs a real source. `-- field
  notes`, `-- night log`, `-- a wise dev` all signal "i invented this quote
  to sound wise." either cite a real artifact (`from ship.md`, `from the
  three-little-workflows post`) or drop the attribution.
- **invented precision.** `3:14 am`, `exactly 47 prs`, `it took 11 minutes
  and 4 seconds` read specific but are made up. if the number/time is real,
  cite a source (commit hash, log line, pr #). if not, don't fabricate.
- **coach register phrases.** `where do you fall?`, `which one are you?`,
  `here's what nobody tells you`, `counterintuitive:`, `unlock your X`,
  `game-changing`, `the ultimate`. all auto-kill.
- **stacked imperatives to the reader.** `pull ship.md. run it on a pr.
  notice where your hand goes.` each line commands the reader to a new
  action. keep ctas to one concrete step or drop the slide.

## source

- `~/code/marshallhouston.wtf/CLAUDE.md` -- canonical voice rules
- `~/code/marshallhouston.wtf/.claude/hookify.*.local.md` -- hard blocks
  (lowercase, no em-dashes, date-only frontmatter, no bare angle brackets)
- `~/code/marshallhouston.wtf/_posts/2026-04-13-three-little-workflows.md` --
  a real post in the target register
- `~/code/marshallhouston.wtf/_posts/2026-03-22-build-friction-fix.md` --
  philosophical register, still grounded
- `~/code/marshallhouston.wtf/_posts/2026-04-22-unpromptable-linkedin-flip.md`
  -- satire. **anti-sample.** never imitate.
- `scripts/check.sh` -- mechanical enforcement of the rules above
