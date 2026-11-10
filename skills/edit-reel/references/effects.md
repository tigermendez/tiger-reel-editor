# Effects catalogue

Each effect has a plain name and a phrase the person can say. Time effects from the words (`.words.json`): the
second a key word starts. One effect per idea; a reel with an effect every second feels cheap.

| Say | Effect | Command |
|---|---|---|
| "zoom de golpe en *palabra*" / "punch in on *word*" | Instant punch-in on the face, held while the word lands | `reel.py fx zoom <video> -o <out> --at <s> [--dur 0.8] [--amount 1.25] [--face face.json]` |
| "que tiemble en el remate" / "shake on the punchline" | Short camera shake | `reel.py fx shake <video> -o <out> --at <s> [--dur 0.5] [--amount 18]` |
| "congela con disco rayado" / "freeze frame with a record scratch" | The frame freezes (the reel gets longer) with a scratch sound | `reel.py fx freeze <video> -o <out> --at <s> [--hold 1.2] [--sound scratch]` |
| "cámara lenta aquí" / "slow motion here" · "acelera esto" | One stretch at another speed | `reel.py fx speed <video> -o <out> --at <s> --dur <s> --factor 0.5` (or 2) |
| "antes y después" / "before and after" | Before on top, after below, labelled | `reel.py fx split <before> <after> -o <out> [--labels "ANTES,DESPUÉS"] [--dur 4]` |
| "texto que se escribe" / "typewriter text" | A fixed sentence typed letter by letter, then kept | `reel.py text <video> "…" -o <out> --typewriter 2` |
| "letras curvas" / "curvy letters" | Fixed sentence bulged like a fisheye lens | `reel.py text <video> "…" -o <out> --fisheye 0.25` (recipe `templates/recipe-serif-yellow.md`) |
| "acércate al botón / a esta parte de la pantalla" / "zoom into this part of the screen" | Smooth zoom into a box of a screen recording and back out (the tutorial zoom) | `reel.py fx focus <video> -o <out> --at <s> --box x,y,w,h [--dur 2.5]` |
| "mi cara en una burbuja" / "my face in a bubble" | Your face in a round bubble in a corner, over a screen or picture | `reel.py fx bubble <screen> <face> -o <out> [--corner bottom-right] [--tight 0.6]` |
| "pantalla arriba, yo abajo" / "screen on top, me below" | Split: screen recording on top, you below, with your sound | `reel.py fx stack <screen> <me> -o <out>` |
| "ponme delante de esta imagen/web" / "green screen without a green screen" | You cut out, in front of a picture, a webpage capture or a video | `reel.py fx backdrop <me> <picture or video> -o <out>` (module graphics) |
| "barra de progreso" / "progress bar" | A thin bar that fills until the end, above the app's bottom bar | `reel.py fx progress <video> -o <out> [--color F8C300]` |
| "un emoji en *palabra*" / "pop an emoji on *word*" | A 3D (or flat) emoji pops with a small bounce | `reel.py fx emoji <video> -o <out> --at <s> --emoji 💸 [--x --y --size] [--style 2D]` |
| "acércate despacio" / "slow push-in" | A slow, continuous push-in over a sentence (not a jump) | `reel.py fx pushin <video> -o <out> --at <s> [--dur 4] [--amount 1.08]` |
| "un destello al cambiar de tema" / "flash transition" | A quick white flash at a topic change (the rest keeps hard cuts) | `reel.py fx flash <video> -o <out> --at <s>` |
| "en blanco y negro hasta el remate" / "black and white, then colour" | B&W (or blurred) until the reveal, then colour | `reel.py fx reveal <video> -o <out> --at <s> [--mode bw\|blur]` |
| "look de película" / "film look" | Soft grain and a vignette (aesthetic reels, not tutorials) | `reel.py fx film <video> -o <out>` |
| "texto detrás de mi cabeza" / "text behind my head" | Big word between the background and the person | `reel.py cutout` + layers (`references/graphics.md`) |
| "subtítulos palabra por palabra" / "word-by-word captions" | 1–2 words at a time, the spoken one in another colour | `reel.py captions … --words 2 --accent FFD400` |
| "fondo borroso" / "blurred background" (wide video) | The same video blurred behind, filling 9:16 | `ff fit <video> --aspect 9:16 --fit blur` |
| "acércame" / "punch in to chest-up" | A tighter frame from a wide shot | `references/pieces.md` (camera) |

Sounds that go with them (`reel.py sfx --list`): `whoosh` for things that slide in, `pop` for things that appear,
`scratch` with a freeze, `impact` with a zoom or shake on the punchline, `riser` before a reveal.

Drawn marks (a circle, an underline, an arrow drawn over what you point at) are best as a HyperFrames layer: its
blocks include marker highlights, circles and scribbles (`reel.py hf catalog`), timed to the word like any graphic.

Left out on purpose, because they cheapen a talking or teaching reel: glitch/RGB split, VHS and low-res looks,
light leaks, 3D cube or spin transitions, cloning yourself, beat-synced speed ramps, an effect on every cut.

## Adding an effect
When the person shows a reel with an effect they want, study it (`reel.py study`, look frame by frame), build it
with ffmpeg-skill or a filter, try it on their footage, and when it works add a row here (or to a recipe) with
its phrase. The catalogue grows with what people ask for.
