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
| "texto detrás de mi cabeza" / "text behind my head" | Big word between the background and the person | `reel.py cutout` + layers (`references/graphics.md`) |
| "subtítulos palabra por palabra" / "word-by-word captions" | 1–2 words at a time, the spoken one in another colour | `reel.py captions … --words 2 --accent FFD400` |
| "fondo borroso" / "blurred background" (wide video) | The same video blurred behind, filling 9:16 | `ff fit <video> --aspect 9:16 --fit blur` |
| "acércame" / "punch in to chest-up" | A tighter frame from a wide shot | `references/pieces.md` (camera) |

Sounds that go with them (`reel.py sfx --list`): `whoosh` for things that slide in, `pop` for things that appear,
`scratch` with a freeze, `impact` with a zoom or shake on the punchline, `riser` before a reveal.

## Adding an effect
When the person shows a reel with an effect they want, study it (`reel.py study`, look frame by frame), build it
with ffmpeg-skill or a filter, try it on their footage, and when it works add a row here (or to a recipe) with
its phrase. The catalogue grows with what people ask for.
