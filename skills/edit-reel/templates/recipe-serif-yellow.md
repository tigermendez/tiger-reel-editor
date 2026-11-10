# Recipe: soft serif in mustard yellow (trend, 2026)

One **fixed sentence** on screen for the whole short clip (a few seconds) — not captions that follow the voice —
in a tall, soft serif (the "curvy letters" look) and a warm mustard yellow, with no outline. Learned from a
trending tutorial reel (the font there is Advercase).

## What makes it this style
- The same text stays on screen the whole clip: one to three centred lines, usually the hook or a thought.
- A tall, narrow serif with soft curves. **Advercase** is the original (a paid font: if the person has the file,
  put it in `fonts/`); **Instrument Serif** (free, Google Fonts) is the closest free match.
- Mustard yellow **#F8C300**; a lighter yellow **#FFF8B5** for one or two marked words. The light one reads best
  over darker parts of the picture.
- No black outline; a soft shadow so it still reads on bright backgrounds.

## What can change freely
Size, height on screen, which words are light, line breaks, italic for one word, a short fade.

## How to build it here
```
reel.py font "Instrument Serif"          # or put the Advercase file in fonts/
reel.py text <clip> "Te enseño a poner estas letras *curvas* porque nadie te dice cómo" -o out/<slug>_v1.mp4 \
  --font fonts/InstrumentSerif/InstrumentSerif-Regular.ttf --size 92 --color F8C300 --accent FFF8B5 \
  --y <a free area: away from the face (reel.py face) and the app's bottom 20 %>
```
Several sentences in a row: run `text` once per sentence with `--start` / `--end`. For titles or cards in the same
look, use the same font file and colours in a graphics layer (`references/graphics.md`).
