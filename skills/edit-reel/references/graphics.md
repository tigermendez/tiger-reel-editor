# Graphics (module `graphics`)

Titles, list counters, cards, data lines and calls to action are made with **HyperFrames** (by HeyGen, Apache-2.0):
HTML + CSS + a GSAP timeline, rendered locally in headless Chrome. `reel.py setup --module graphics` installs a
pinned copy (Node.js 18+ required) and its Chrome; `reel.py hf <command>` runs that copy.

For HyperFrames' own authoring rules (blocks, animation, fonts, `lint`, `check`), use the official skills: they
come with `reel.py hf init` (or `npx skills add heygen-com/hyperframes`). This file is only how graphics fit a reel.
Remotion is a fine alternative if the person already uses React; the checks below apply the same way.

## The method: a transparent layer over the cut

1. **Cut first.** Graphics are timed to the final cut, never to the raw footage.
2. **Measure.** `reel.py face <cut> --json face.json` (where the face is) and the cut's `.words.json` (when each
   word is said). Time every element from the words: a list item appears on the first word of its line.
3. **Compose** `graphics/index.html` at 1080x1920, `background: transparent`, same duration as the cut. Generate it
   from a small script (`out/graphics.py`) that reads the words, so a changed take re-times everything.
   Mark every element that must not collide with `data-check="name"`.
4. **Check before rendering:** `reel.py overlaps graphics --face face.json` — exit 1 lists what overlaps what, and
   what covers the face, with the seconds. Fix the layout, not the check. Then
   `reel.py hf check graphics --at <the second each element is on screen>`: it also finds text that spills out
   of its box (`text_box_overflow`). Inline text with `<b>` inside a flex card must be wrapped in one `<span>`,
   or each piece becomes its own line.
5. **Render the layer:** `reel.py hf render graphics --format webm -o out/overlay.webm --quiet` (VP9 with alpha;
   `--format mov` gives ProRes 4444, much larger).
6. **Lay it over the cut:** `ff overlay <cut> --video out/overlay.webm --position center --scale 1080 --margin 0`,
   then the usual `ff export --preset reels`, `reel.py level` and `reel.py review`.
7. **Look** at frames where each element enters; check text size on a phone-sized view.

## Text behind the head

`reel.py cutout <cut> -o out/person.webm` cuts the person out of the final cut (HyperFrames' local model, ~170 MB
the first time; about 5–6 s of processing per second of video on an M4). Then stack three layers:

1. the cut;
2. the text or graphic (`ff overlay --text` for plain text, or a HyperFrames layer for styled text);
3. the cutout on top: `ff overlay <cut+text> --video out/person.webm --position center --scale 1080 --margin 0`.

Place the text so it crosses the top of the head (use `reel.py face` for where the head is): the head hides part
of the letters and they read as being behind it. Use it for the one word that matters, not as a habit. Hair,
hands and fast movement can leave rough edges: look at the frames.

## Fonts
Use font files, not installed fonts, so the render is the same on every computer: copy the file from the project's
`fonts/` (get one with `reel.py font "<Family>"`) into the graphics folder and declare it:
`@font-face { font-family: "Bebas Neue"; src: url("BebasNeue-Regular.ttf"); }`.

## Layout rules that work for vertical video

- The top ~240 px belong to the app's own interface; the bottom ~20 % and the right ~12 % too (`review.md`).
- Leave the face free. If a panel goes on top, frame the shot with the head lower (crop from the top of a
  punched-in render) and confirm with `face` before designing.
- One idea on screen at a time; short text (3–5 words), big (60–90 px), high contrast, a dark translucent box
  behind text over busy backgrounds.
- Entrances short (0.15–0.3 s); no spins, cubes or flashes. Colour can group items (one colour per section).
- Numbers and facts on screen must be true and sourced; the person approves every text.

## Example

A list reel ("25 things to check before launching your web app"): a translucent panel at y 250–610 with a fixed
title, then each item as `N/25 + text`, coloured by section, appearing on the first word of its line; a data line
during the hook; a "Comment WEB" card on the closing line. About 150 lines of Python generating the HTML,
42 s to render 60 s of overlay on an M4, zero overlaps with the face.
