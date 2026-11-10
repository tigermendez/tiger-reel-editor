# Recipe: list to camera (example)

Learned from: a 60 s talking-head reel listing 25 tips (study/list-to-camera). Use it as a starting point.

## What makes it this style
- One person to camera, chest-up, head in the lower half; the top third is for a translucent panel.
- The panel shows the item being said: small fixed title on top, `N/25` counter, the item in 2–5 big words.
- Something new on screen about every 1.2 s (jump cuts between takes + each item entering).
- Each section has its own colour (e.g. security yellow, legal blue, findability green, function pink).
- Fast, plain speech (~160 words/min), no music, no intro: the first word is at 0.2 s.

## What can change freely
Fonts, the exact colours, the number of items, word-by-word captions or none, effects, the closing card, length.

## Measured
60.7 s · 1 big cut · something new every 1.21 s · 158 words/min · speech 56 % of the time · −14.2 LUFS.

## How to build it here
- Framing: punch in 1.5x and crop with the forehead near 640 px (`references/pieces.md`, camera).
- Panel: HyperFrames layer, translucent box at y 250–610, title 30 px, counter 34 px, item 76 px bold; each item
  enters on the first word of its line (0.18 s slide-up). Check with `reel.py overlaps` and `reel.py hf check`.
- Captions: none (the panel already says each item); if wanted, `--y` below the chin from `reel.py face`.
- Effects: a soft `pop` on each item (−4 dB), `whoosh` on the hook and the closing card.
- Loudness: `reel.py level`.
