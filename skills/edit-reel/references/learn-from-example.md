# Learning from an example

The person brings whatever they have: a video (theirs or anyone's), screenshots, a template, a link they
downloaded themselves, or only a description ("like the reels of X: yellow words, fast"). Whatever they bring is
their call. Turn it into a **recipe** they can reuse: `recipes/<name>.md` in their project.

## 1. Measure what can be measured
- A video: `reel.py study <video> -o study/<name>` → `hook.jpg` (the first 3 s, 12 frames), `sheet.jpg` (40 frames
  over the whole video), `cuts.txt` and `stats.json`: length, big cuts, **something new every N s** (jump cuts and
  graphics entering), loudness, words per minute, when the first word starts, how much of it is speech, and the
  transcript.
- Screenshots or a template: look at them directly.
- Only words: ask one or two questions (an example frame, or two adjectives), then propose.

## 2. Look, then write the recipe
Open the images and note, concretely: where text sits (px from the top), how big, the font family or its look
(condensed sans, serif, handwritten), colours (hex), how captions enter (word by word, 2 words, karaoke), what
graphics appear and how often, the hook's first frame, framing (face size, headroom), and the sound (music,
effects, silence). If a font is identifiable, name it; get it with `reel.py font "<Family>"` or ask for the file.

Write the recipe from `templates/recipe.example.md`. Always separate:
- **What makes it this style** — the 3–6 things that, if changed, it stops looking like it.
- **What can change freely** — everything else, so the recipe never becomes a cage.
- **Measured** — the numbers from `stats.json`.
- **How to build it here** — the exact `captions` flags, the graphics layout, effects cues, fonts files.

Show it to the person in plain words ("this style is: big yellow words in the middle, something new every second,
no music"), adjust, and save it.

## 3. Use it, mix it, grow it
- "Do it like recipe X" → follow its build section; "X but calmer" → keep its essence, change the rest.
- Recipes mix: captions from one, graphics from another.
- Anything no recipe covers is still possible: build it with HyperFrames or ffmpeg-skill. Nothing is fixed in code.
- When something works, offer to save it: a one-off correction goes to `style.md`; a new look becomes a recipe.
