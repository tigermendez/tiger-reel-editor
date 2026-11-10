# Recipe: soft serif in mustard yellow (trend, 2026)

Captions as short sentences in a tall, soft serif — the "curvy letters" look that many edits use — in a warm
mustard yellow, with no outline. Learned from a trending tutorial reel (the font there is Advercase).

## What makes it this style
- A tall, narrow serif with soft curves. **Advercase** is the original (a paid font: if the person has the file,
  put it in `fonts/`); **Instrument Serif** (free, Google Fonts) is the closest free match.
- Mustard yellow text **#F8C300**; a lighter yellow **#FFF8B5** for the word being said (or for a second line).
- Whole short sentences (one or two lines, centred), not one or two words at a time.
- No black outline; a soft shadow so it still reads on bright backgrounds.

## What can change freely
Size, height on screen, the accent (or none), sentence length, italic for one word, animation.

## How to build it here
```
reel.py font "Instrument Serif"          # or put Advercase.otf/ttf in fonts/
reel.py captions out/cut.words.json out/captions.ass --words 9 --max-chars 48 --gap 0.6 --wrap 760 \
  --size 96 --font fonts/InstrumentSerif/InstrumentSerif-Regular.ttf --color F8C300 --accent FFF8B5 \
  --outline 0 --shadow 3 --y <below the chin, from reel.py face>
ff caption out/cut.mp4 --ass out/captions.ass --fonts-dir fonts/InstrumentSerif
```
For graphics (titles, cards) in the same look: `@font-face` with the same file and the same two colours
(`references/graphics.md`).
