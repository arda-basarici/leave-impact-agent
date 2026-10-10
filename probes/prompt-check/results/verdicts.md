# The correct-whole verdict of every prompt-check run, from the captured exports

Read back by `verdicts.py` with the real evaluator over the exports the probe captured; a run's verdict is the preregistration's first check, whether its report is correct in every part against the expected answer. `yes`, `no`, or `-` for a run the evaluator did not grade. The structured scenarios (009, 010) rest on the prefetch alone, so their verdict says nothing of the prompt; the seventh run (014) is the chain check's.

| round | scenario_009 | scenario_010 | scenario_013 | scenario_014 | scenario_018 | scenario_023 | scenario_028 | correct whole of n |
|---|---|---|---|---|---|---|---|---|
| shipped | yes | yes | no | yes | no | no | no | 3 of 7 |
| search-by-names | yes | yes | no | yes | no | no | no | 3 of 7 |
| search-plan | yes | yes | no | yes | yes | yes | no | 5 of 7 |
| search-once | yes | yes | no | yes | no | yes | yes | 5 of 7 |
| closed-list | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| accurate-search | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| rm-first-message | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| rm-one-instant | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| rm-tool-shape | yes | yes | yes | yes | yes | yes | yes | 7 of 7 |
| rm-any-turn | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| rm-stop-reading | yes | yes | yes | yes | yes | yes | yes | 7 of 7 |
| rm-stated-before | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| rm-no-more-reads | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| final-set | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
| final-set-repeat | yes | yes | no | yes | yes | yes | yes | 6 of 7 |
