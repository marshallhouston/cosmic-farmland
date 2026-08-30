# slideshow / assets

Brand files referenced by `templates/_base.css`. Drop real files here when they're ready, then update the matching CSS variables at the top of `_base.css`.

## Expected files

| File | CSS var | Notes |
|---|---|---|
| `logo.svg` | `--brand-logo-url` | Small wordmark/logo. Rendered at 120x40 top-left. Prefer SVG so it stays crisp. |
| `watermark.png` | `--brand-watermark-url` | Optional decorative image anchored to the bottom of every slide. PNG with transparency, at least 1080px wide. Set the CSS var to `url("../assets/watermark.png")` to turn it on -- it's `none` by default. |
| Fonts (optional) | `--brand-font-display`, `--brand-font-body`, `--brand-font-mono` | If shipping custom fonts, drop `.woff2` files here and add an `@font-face` block to the top of `_base.css`. |

## Tokens

Update these in `_base.css` once the brand is locked:

```css
--brand-bg: /* slide background */;
--brand-ink: /* primary text */;
--brand-ink-soft: /* secondary text */;
--brand-accent: /* accent (headlines, rules, stats) */;
--brand-accent-soft: /* lighter accent (terminal prompt, etc.) */;
```

## Swapping the wordmark for a logo image

The templates render the wordmark via a text fallback:

```html
<div class="brand-logo-fallback">cosmic-farmland</div>
```

Once `logo.svg` is in place, replace that line in each template with:

```html
<div class="brand-logo"></div>
```

(or do a find-and-replace across `templates/*.html`).
