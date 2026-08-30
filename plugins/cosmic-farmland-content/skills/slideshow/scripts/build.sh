#!/usr/bin/env bash
# slideshow/scripts/build.sh
#
# Render a directory of slide-NN.html files into:
#   slide-NN.png  -- one 1080x1350 PNG per slide
#   slideshow.pdf -- single combined PDF for LinkedIn upload
#
# Usage: build.sh <slideshow-dir>
# The <slideshow-dir> must contain _base.css and slide-01.html ... slide-NN.html.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: build.sh <slideshow-dir>" >&2
  exit 64
fi

dir="$1"
if [[ ! -d "$dir" ]]; then
  echo "error: not a directory: $dir" >&2
  exit 66
fi

dir="$(cd "$dir" && pwd)"

# Locate a headless Chrome/Chromium binary.
find_chrome() {
  local candidates=(
    "${CHROME:-}"
    "google-chrome"
    "google-chrome-stable"
    "chromium"
    "chromium-browser"
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "/Applications/Arc.app/Contents/MacOS/Arc"
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  )
  for c in "${candidates[@]}"; do
    [[ -z "$c" ]] && continue
    if [[ -x "$c" ]]; then echo "$c"; return 0; fi
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return 0; fi
  done
  return 1
}

chrome="$(find_chrome)" || {
  echo "error: no Chrome/Chromium found. Set CHROME env var to the binary path." >&2
  echo "hint: on macOS install Google Chrome, or run: brew install --cask chromium" >&2
  exit 69
}

echo "chrome: $chrome"
echo "dir:    $dir"

if [[ ! -f "$dir/_base.css" ]]; then
  echo "error: missing _base.css in $dir -- slides will render unstyled." >&2
  echo "hint: copy templates/_base.css into the output dir before building." >&2
  exit 66
fi

shopt -s nullglob
slides=( "$dir"/slide-*.html )
if [[ ${#slides[@]} -eq 0 ]]; then
  echo "error: no slide-*.html files in $dir" >&2
  exit 66
fi

log="$dir/.slideshow-build.log"
: > "$log"

# Run voice checks before rendering. Non-zero from check.sh aborts the
# build. Override a specific run with SLIDESHOW_SKIP_CHECK=1 if you have
# a real reason (rare).
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! "$script_dir/check.sh" "$dir"; then
  exit 1
fi

# Sort slides by filename so slide-01 comes before slide-02 ... slide-10.
IFS=$'\n' slides=( $(printf '%s\n' "${slides[@]}" | sort) )
unset IFS

echo "slides: ${#slides[@]}"

# 1) Render each slide to PNG. We render at 2x device scale so the
#    bitmap stays crisp when a viewer zooms into the PDF. PDF page
#    geometry stays 1080x1350 px; the embedded image just has 4x the
#    pixels (2160x2700). Override with SLIDESHOW_DPR=1 or 3 if needed.
dpr="${SLIDESHOW_DPR:-2}"
for slide in "${slides[@]}"; do
  base="$(basename "$slide" .html)"
  out="$dir/$base.png"
  echo "  -> $base.png (dpr=$dpr)"
  if ! "$chrome" \
      --headless=new \
      --disable-gpu \
      --no-sandbox \
      --hide-scrollbars \
      --default-background-color=00000000 \
      --force-device-scale-factor="$dpr" \
      --window-size=1080,1350 \
      --screenshot="$out" \
      "file://$slide" \
      >>"$log" 2>&1; then
    echo "error: chrome failed rendering $slide -- see $log" >&2
    exit 1
  fi
done

# 2) Build a combined print HTML that embeds the PNGs we just rendered,
#    then print to PDF. Using PNGs (not iframes) keeps pagination reliable
#    across Chrome versions.
print_html="$dir/.slideshow-print.html"

{
  cat <<'HEAD'
<!doctype html><html><head><meta charset="utf-8">
<style>
  @page { size: 1080px 1350px; margin: 0; }
  html, body { margin: 0; padding: 0; background: transparent; }
  .page { width: 1080px; height: 1350px; display: block; page-break-after: always; }
  .page:last-child { page-break-after: auto; }
  img { display: block; width: 1080px; height: 1350px; }
</style>
</head><body>
HEAD
  for slide in "${slides[@]}"; do
    base="$(basename "$slide" .html)"
    printf '<div class="page"><img src="%s.png"></div>\n' "$base"
  done
  echo "</body></html>"
} > "$print_html"

pdf_out="$dir/slideshow.pdf"
echo "  -> slideshow.pdf"

if ! "$chrome" \
    --headless=new \
    --disable-gpu \
    --no-sandbox \
    --no-pdf-header-footer \
    --print-to-pdf="$pdf_out" \
    "file://$print_html" \
    >>"$log" 2>&1; then
  echo "error: chrome failed printing PDF -- see $log" >&2
  exit 1
fi

rm -f "$print_html" "$log"

echo
echo "done."
echo "  pdf:  $pdf_out"
echo "  pngs: $dir/slide-*.png"
