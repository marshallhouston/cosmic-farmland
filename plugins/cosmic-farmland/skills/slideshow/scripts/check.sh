#!/usr/bin/env bash
# slideshow/scripts/check.sh
#
# Grep slide HTML + caption for known voice violations before rendering.
# Non-zero exit blocks the build. Override a specific failure with
# SLIDESHOW_SKIP_CHECK=1 when you have a real reason (rare).
#
# Usage: check.sh <slideshow-dir>
#
# The rules here all came from real dogfood failures. Add to this list
# when a review surfaces a new one. Each rule has:
#   - a pattern (grep -E)
#   - a one-line explanation that will appear in the error
#   - a fix hint

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: check.sh <slideshow-dir>" >&2
  exit 64
fi

dir="$1"
if [[ ! -d "$dir" ]]; then
  echo "error: not a directory: $dir" >&2
  exit 66
fi

if [[ "${SLIDESHOW_SKIP_CHECK:-}" == "1" ]]; then
  echo "check: skipped via SLIDESHOW_SKIP_CHECK=1"
  exit 0
fi

shopt -s nullglob
targets=( "$dir"/slide-*.html )
[[ -f "$dir/caption.txt" ]] && targets+=( "$dir/caption.txt" )
if [[ ${#targets[@]} -eq 0 ]]; then
  echo "check: no slide-*.html or caption.txt in $dir, nothing to check"
  exit 0
fi

fail=0
report() {
  local rule="$1" hint="$2" file="$3" match="$4"
  echo "VOICE CHECK FAIL [$rule]" >&2
  echo "  file:  $file" >&2
  echo "  match: $match" >&2
  echo "  fix:   $hint" >&2
  echo "" >&2
  fail=1
}

# Rule 1: em-dash / en-dash. Hardlocked by hookify on the site; same here.
for f in "${targets[@]}"; do
  while IFS= read -r line; do
    [[ -n "$line" ]] && report "em-dash" \
      "replace with '.', ',', or '--' (double hyphen)" "$f" "$line"
  done < <(grep -nE $'—|–' "$f" || true)
done

# Rule 2: fake-source attribution. Pull-quote attributions that read like
# the writer invented the source. Known-bad list, expand as needed.
for f in "${targets[@]}"; do
  while IFS= read -r line; do
    [[ -n "$line" ]] && report "fake-source-attribution" \
      "quote a real source (a file, a doc, a person) or drop the attribution" \
      "$f" "$line"
  done < <(grep -nEi '(field notes|anonymous|night log|a wise (dev|friend))' "$f" || true)
done

# Rule 3: invented precision. Fabricated timestamps/counts that did not
# actually happen. Matches e.g. '3:14 am', 'at 2:47pm', 'exactly 47 prs'.
# False positives possible; if a number is real, cite it.
for f in "${targets[@]}"; do
  while IFS= read -r line; do
    [[ -n "$line" ]] && report "invented-precision" \
      "if the number/time is real, cite it (commit hash, pr number, timestamp from the log). if not, drop it." \
      "$f" "$line"
  done < <(grep -nEi '\b[0-9]{1,2}:[0-9]{2} ?(am|pm)\b' "$f" || true)
done

# Rule 4: LinkedIn-coach register. Phrases flagged in VOICE.md as
# auto-kills.
coach_patterns='where do you fall|where do you stand|which one are you|here.?s what|the surprising truth|counterintuitive[:;]|unlock your|game.?chang|transformational|the ultimate'
for f in "${targets[@]}"; do
  while IFS= read -r line; do
    [[ -n "$line" ]] && report "coach-register" \
      "rewrite without the workshop phrasing (see VOICE.md 'kill' list)" \
      "$f" "$line"
  done < <(grep -nEi "$coach_patterns" "$f" || true)
done

# Rule 5: Title Case in headings/headlines/kickers/cta. Crude heuristic:
# inside a headline/subhead/kicker/cta-line tag, flag content that starts
# with a capital letter followed by lowercase (skip if the first word is
# a known proper noun).
proper_nouns='GitHub|Jekyll|LinkedIn|Instagram|Claude|Anthropic|OpenAI|BFF|PTVM|ADHD|CI|PR|CPU|GPU|API|HTML|CSS|PDF|URL|YAML|JSON|CLI|SDR'
for f in "$dir"/slide-*.html; do
  while IFS= read -r line; do
    # Strip the wrapping tag to get just the text content
    txt=$(echo "$line" | sed -E 's/^[^>]*>//; s/<.*$//')
    # Skip empty, skip proper-noun starts, skip all-caps
    [[ -z "$txt" ]] && continue
    first=$(echo "$txt" | awk '{print $1}')
    [[ "$first" =~ ^($proper_nouns)$ ]] && continue
    [[ "$first" =~ ^[A-Z]+[[:punct:]]?$ ]] && continue
    # Title-Case-style first word: starts uppercase, has lowercase inside
    if [[ "$first" =~ ^[A-Z][a-z] ]]; then
      report "title-case" \
        "headings/headlines/kickers should be lowercase (VOICE.md)" \
        "$f" "$line"
    fi
  done < <(grep -nE '<(h1|h2)[^>]*class="(headline|subhead|cta-line)"[^>]*>|<div[^>]*class="kicker"[^>]*>' "$f" || true)
done

if [[ "$fail" -eq 1 ]]; then
  echo "check: voice violations above block the build." >&2
  echo "       fix the copy or set SLIDESHOW_SKIP_CHECK=1 with a real reason." >&2
  exit 1
fi

echo "check: ok"
