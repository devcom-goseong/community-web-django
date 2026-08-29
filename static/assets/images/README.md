# Images

Every file here is generated from `design/logo-master.png` by
`design/build-assets.py`. If you change the logo, update that script's crop
boxes and re-run it from the project root:

    python design/build-assets.py

Do not hand-edit these files — the next run overwrites them.

| File | Size | Where it appears |
| --- | --- | --- |
| `logo-mark.png` / `.webp` | 320 x 38 | The three-ellipse mark in the header |
| `logo-mark-inverse.png` / `.webp` | 320 x 38 | The same mark on the ink footer and bands |
| `hand.png` / `.webp` | 894 x 1200 | The hero on the home page, and the 404 page |
| `logo-full.png` / `.webp` | 1600 x 1092 | The complete lockup. Print, slides, social profiles |
| `wordmark.png` / `.webp` | 1100 x 146 | "Dev Community" on its own. Currently unused on the site |
| `wordmark-inverse.png` / `.webp` | 1100 x 146 | The same, for dark backgrounds |
| `chevron.png` / `.webp` | 560 x 490 | The drawn chevron. Currently unused on the site |
| `chevron-inverse.png` / `.webp` | 560 x 490 | The same, for dark backgrounds |
| `og-image.png` | 1200 x 630 | The social sharing card in every page's meta tags |

## Notes

- The PNGs are 8-bit greyscale **with an alpha channel**, so the ink sits on
  any background without a white box around it. The tone is baked in at
  `#0d0d0d`, matching `--color-ink`.
- WebP versions exist for the two images large enough to matter. The HTML uses
  `<picture>` so older browsers fall back to the PNG automatically.
- The `width` and `height` attributes in the HTML match the table above. If you
  replace a file at a different size, update the attributes too or the page
  will shift while loading.
- `og-image.png` is drawn with Georgia, not Bodoni Moda, because the card is
  rendered by a script rather than a browser. Replacing it with a proper export
  from a design tool is a fine idea — keep it 1200 x 630.
