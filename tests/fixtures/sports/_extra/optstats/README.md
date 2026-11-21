# Optstats (test sport)

Used only by `tests/test_option_stats.py`. One stat group, `player`: AB and H while `batting` is `optional` or
`every_game`, BB only with `every_game`, and the rate AVG. The sheet:

    final: {home: 3, away: 2}
    batters: {home: [{player: a1, ab: 3, h: 2, bb: 1}], away: [...]}

`batting: order` keeps a line for each batter with no numbers; `none` keeps no line at all.
