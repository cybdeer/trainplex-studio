# Reel 02 takes QA

Generated 2026-10-01 17:43 by `work/qa_take.py`. Transcript columns use the unprompted whisper pass; a word is taken from the script-prompted pass only where the unprompted pass heard nothing or a near-spelling there (`*` = passes only thanks to such rescues). Prompted-pass words with ~0 s duration or prob < 0.30 are treated as prompt echo and ignored. Face sim = insightface cosine vs `flow/character/char_01_master.png`, flag < 0.45. eye_y target ~0.35.

| clip | take | transcript_ok | match | missing / wrong words | numbers ok | TrainPlex ok | cut off | face sim min / mean | eye_y | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | NO | 0.74 | क्योंकि, मैं, पे→I, काम→work, करती→on, हूँ→trainplex. | yes | yes | no | 0.597 / 0.706 | 0.32 | FAIL (transcript) |
| 1 | 2 | yes | 1.00 | - | yes | yes | no | 0.505 / 0.67 | 0.317 | PASS |
| 2 | 1 | yes | 1.00 | - | yes | n/a | no | 0.535 / 0.674 | 0.406 | PASS |
| 2 | 2 | yes | 0.95 | से→कॉर्ड, | yes | n/a | no | 0.667 / 0.73 | 0.419 | PASS |
| 3 | 1 | yes | 0.96 | available→अवेलिबल | yes | n/a | no | 0.482 / 0.594 | 0.42 | PASS |
| 3 | 1 | yes | 1.00 | - | yes | n/a | no | 0.447 / 0.6 | 0.423 | REVIEW (face similarity / detection) |
| 3 | 2 | yes | 0.96 | available→अवेलिबल | yes | n/a | no | 0.561 / 0.654 | 0.417 | PASS |
| 3 | 2 | yes | 1.00 | - | yes | n/a | no | 0.573 / 0.642 | 0.422 | PASS |
