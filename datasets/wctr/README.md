# wCTR prediction smoke fixture

This is a small synthetic fixture for checking the ResearchOS and Evo monitor
integration. The connected bicycle demo does not currently contain the
historical `bicycle.csv`, so these numbers are not a claim about the May 2024
campaign and must not be ingested as a research result.

`train.csv` and `test.csv` have disjoint `impression_id` values. The benchmark
learns smoothed segment CTR from train and reports held-out log loss and wCTR
on test. Replace the fixture with the real bicycle export before drawing a
substantive conclusion.
