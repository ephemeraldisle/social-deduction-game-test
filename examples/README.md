# Featured replays

Only saves explicitly listed in `manifest.json` are included in the public site.
The three Astra launch playthroughs use fresh `gpt-6-astra` agents, each given
only the public participant documents and a seat-only bridge. They record a
short explanation for each chosen action and allegiance predictions after
every mission, including the final one. All three prespecified games are kept.

This is procedural blindness, not an OS sandbox: the agents were instructed
not to inspect source, saves, seeds, previous games, or other seats. The run
provenance and verification summary are in [provenance.md](provenance.md).
In the replay viewer, enable **Reveal all** to see Astra's checkpoint
predictions and recorded decision explanations, or click a scripted bot to see
its latest saved player rankings at that moment.

To add another completed current-rule Astra run, copy its `session.json` here
and add an entry:

```json
[
  {
    "file": "astra-01.json",
    "title": "Astra · First playthrough",
    "description": "Follow Astra’s decisions and changing team predictions."
  }
]
```

The save already includes recorded explanations and team predictions. Do not
copy API transcripts, credentials, or the entire run directory. The build loads
and verifies each selected save and refuses unfinished or incompatible games.
Featured games appear as read-only replays; they do not modify visitors' saves.

Generate these after the launch rules are settled. Changed rules may require
new examples; old saves are not migrated.
