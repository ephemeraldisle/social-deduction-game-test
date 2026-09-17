# AI CLI playthrough — Table 762F3D

> **Not a blind AI evaluation.** The playing assistant read repository source
> before this game. This run is a CLI/replay smoke test only and does not
> satisfy the requirement that the player agent have no source-code access.
> A valid evaluation requires a fresh player context with no repository or
> filesystem access, receiving only the public guide and seat observations
> from a separate trusted runner.

Codex played Abby (seat 0) through `python3 -m mission_game.cli agent`
against seven `social.11` scripted opponents. New-game defaults were used:
`configs/development_abilities.json`, rules `0.1-abilities-dev.3`.
The deal was random, with no seed selection or retries. All 35 external
decisions were made from Abby's CLI observations. Other players' cards and
the authoritative save were inspected only after the game finished.

**Result: Blue won 4–1 in seven resolved attempts. Abby won personally.**
Abby was Blue with Reliable Partner and Auditor. Her 12-Blue payment on
attempt 4 and 4-Blue payment on attempt 6 exactly matched their pledges,
satisfying her objective. She paid nine Blue on the final attempt and
finished with zero tokens.

[Watch from Abby's perspective](http://127.0.0.1:8765/#replay/762f3d41-fa75-4549-8c96-531cf3c021cc?seat=p0).
Enable **Designer view** to inspect hidden actions and decision explanations.
Codex's choices are labeled `codex-cli.1`; the other players retain their
original Social policy explanations.

## Moments to review

- **Opening negotiations:** seven total rejected proposals occurred across
  the game, four before the first approved attempt. Abby's proposed 16-Blue
  funding for a 15-token mission was rejected 4–4. Funding alone did not
  ensure agreement.
- **Attempt 3, deception:** Drew pledged 16 Blue, paid 17 Red, and reported
  17 Blue. Abby voted No before the result based on Drew's earlier voting
  pattern, but the crew passed. Her subsequent audit verified the original
  Red payment. [Inspect that audit choice](http://127.0.0.1:8765/#replay/762f3d41-fa75-4549-8c96-531cf3c021cc?seat=p0&designer=true&position=234).
- **Attempt 4, cooperation:** Abby paid her promised 12 Blue. Harper's
  audited 17 Blue corroborated his pledge. Abby reported both payments
  truthfully, and Blue moved ahead 2–1.
- **Attempt 6, personal objective:** Abby proposed herself, Ben, and Gray,
  then matched her four-Blue pledge. Blue led 3–1 and Reliable Partner
  reached 2/2. [Inspect the payment](http://127.0.0.1:8765/#replay/762f3d41-fa75-4549-8c96-531cf3c021cc?seat=p0&designer=true&position=422).
- **Attempt 7, finishing:** Abby rejected a crew containing both Drew and
  Ellis, then supported a revised crew whose likely Blue payments could
  outweigh Drew. She paid one above her pledge because her two prior exact
  matches already qualified. The final pot was 28 Blue.
  [Inspect the final payment and rationale](http://127.0.0.1:8765/#replay/762f3d41-fa75-4549-8c96-531cf3c021cc?seat=p0&designer=true&position=501).

## Playtest observations

The CLI supported a complete external-agent game without invalid actions,
crashes, or intervention in the engine. Audits were strategically useful:
they separated actual deposits from claims and hidden modifications.
Personal objectives created meaningful choices about participation,
exact payments, and when to spend reserves.

One communication limitation stood out: an off-crew Auditor cannot report
immediately, and a later report cannot name a previous attempt. Abby learned
that Drew had lied on attempt 3 but could only express a generic player
objection in later votes. This is a design question for future playtests,
not a transport failure.

In the postgame reveal, Fran was Red with Spendthrift and Standard Bearer.
Her public Red badge made recruitment difficult; she finished with 25
tokens and no approved crew participation. This interaction is worth
testing across more deals. One Blue win does not establish balance or a
reliable AI win rate.

## Recording and verification

- `session.json`: GUI-ready replay with original game state and action log.
- `cli-session-original.json`: untouched CLI save before attaching AI notes.
- `cli-transcript.jsonl`: full CLI output and submitted action envelopes.
- `ai-decisions.jsonl`: 35 actions and brief reasons written before submission.
- `metrics.json`: game outcomes and counts.
- `replay-verification.txt`: CLI replay verification and seat-0 history.

All **521 recorded actions**, including automatic cover slots, replayed to
the exact saved engine state. Decision notes were joined afterward by
request ID as designer metadata; actions, cards, controller states, and
results were unchanged. Chrome displayed the verified replay and the
saved Codex explanation at the final payment.

If the local server has stopped, restart it from the repository root:

```sh
python3 -m mission_game.cli web --runs-dir runs --port 8765
```

The library lists this game as **Table 762F3D**. The run directory is
ignored by Git, like the project's other saved games.
