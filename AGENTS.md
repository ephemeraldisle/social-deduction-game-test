# Working on this game

Use the minimum validation needed to keep the game functioning. The default
check is `make test`: current-rule engine smoke checks and a few client checks.
For a small change, run only the relevant part. Do not run the historical full
test discovery, replay audit batches, or large bot simulations unless requested
or a concrete failure requires them. Old replay integrity and exact historical
bot behavior are not compatibility requirements. Outdated saved games may be
rejected; do not add migrations just to preserve them.
