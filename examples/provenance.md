# Astra launch playthroughs — September 23, 2026

Three fresh `gpt-6-astra` agents played independently, each with no inherited
conversation and seven Social bot opponents. Each agent received only the
public participant documents and its seat's observations through a trusted
bridge. Source code, saved state, seeds, earlier playtests, and other seats
were excluded by instruction. This is procedural blindness, not an OS sandbox.
All three prespecified games were retained regardless of outcome.

The games use rules `0.1-abilities-dev.5` and `social.16` opponents. Engine and
policy source hashes remained unchanged throughout play. Astra supplied a
short explanation for every chosen action and eight allegiance probabilities
after each mission, before receiving subsequent decisions or observations.
These estimates describe its judgments and are not calibrated probabilities.

| Save | Astra seat | Actions explained | Mission predictions | Score (Blue–Red) |
| --- | --- | ---: | ---: | --- |
| [astra-01.json](astra-01.json) | Jamie (p0) | 31 | 5 | 4–1 |
| [astra-02.json](astra-02.json) | Casey (p3) | 29 | 5 | 4–1 |
| [astra-03.json](astra-03.json) | Sasha (p6) | 26 | 5 | 1–4 |

All three completed games replayed exactly. Each prediction's recorded
observation hash matched the seat observation reconstructed at its action
position. Confirmed teams and the five-Blue total were checked; explanations
matched accepted actions. The saved replays contain this review metadata.

The static browser build loaded all three examples, displayed their mission
predictions and selected bots' rankings, and hid later predictions when
rewound. Desktop and mobile views were checked with no page errors or requests
to external hosts or a game API.

Raw run logs and historical diagnostics stay in the ignored local `runs/`
directory. Only the saves listed in [manifest.json](manifest.json) are bundled
into the public site.
