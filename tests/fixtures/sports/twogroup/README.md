# Twogroup (test sport)

Two stat groups, `skater` (G, A) and `goalie` (GA, SA, and the rates GAA and SV% that only goalies get). Used by
`tests/test_stat_groups.py`. The sheet:

    final: {home: 3, away: 2}
    decided: shootout                       # optional: overtime | shootout
    skaters: {home: [{player: ann-b, g: 1, a: 2}], away: [...]}
    goalies: {home: [{player: gus-t, ga: 2, sa: 20}], away: [...]}
