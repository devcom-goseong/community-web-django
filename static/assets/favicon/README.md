# Favicons

Generated from the chevron in `design/logo-master.png` by
`design/build-assets.py`. The chevron is used rather than the hand because it
is the only part of the mark that stays legible at 16 pixels.

| File | Purpose |
| --- | --- |
| `favicon.ico` | 16 / 32 / 48 bundle, for older browsers and Windows |
| `favicon-16.png`, `favicon-32.png` | Browser tab |
| `favicon-48.png` | Source for the .ico |
| `apple-touch-icon.png` | 180 x 180, iOS home screen |
| `icon-192.png`, `icon-512.png` | Android / web manifest |

The small sizes are drawn with a gamma boost so the thin drawn strokes stay
dark. If you regenerate them and they look faint, lower the `boost` value in
`build-assets.py` — smaller means darker.

The transparent favicons are deliberately transparent so they work in both
light and dark browser themes. The app icons sit on `#f2f2f2` because iOS and
Android composite them onto their own backgrounds.
