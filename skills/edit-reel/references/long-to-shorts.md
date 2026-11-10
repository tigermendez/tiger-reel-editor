# One long video → several reels

For a podcast, a live, a class or a long talking video. The tools exist already; the judgement is the work.

1. **Transcribe the whole thing:** `reel.py transcribe long.mp4 out/long --language <xx> --names "..."`. On a 10-core
   Apple M4 an hour takes about 12 minutes.
2. **Propose moments by meaning, not by volume.** Read `out/long.txt` and the timed words, and propose 5–10 candidate
   reels. Each one: a hook line said in the video (the first thing heard), a self-contained idea with an ending,
   30–60 s, start and end times taken from `.words.json` (first word's start − 0.1 s, last word's end + 0.15 s).
   Show them as a short list: number, hook, time range, one line on why it works. The person picks.
   `ff scenes long.mp4 --highlights 6 --target 45` ranks loud or busy moments; use it only as a second opinion:
   it measures energy, not what is interesting.
3. **Each picked moment becomes its own reel project** (`reel.py new <slug>`), cut with `ff cut --start --end`
   (or a render project if it needs several pieces), then the normal flow: reframe to 9:16 (`ff fit --aspect 9:16
   --fit crop`, or `blur` for wide shots with several people), transcribe the clip, captions, `face`, `level`,
   `review`.
4. **Context check:** a moment cut out of a long talk can change its meaning. Read the sentences before and after;
   if the clip says something the person would not stand behind on its own, drop it or say so.
