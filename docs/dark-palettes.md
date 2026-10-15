# Dark palettes (from the design canvas, round 1)

> **Note (stage 3).** These are the colours as the mockups drew them. The CSS in
> `assets/css/layouts/<id>.css` is now the source of truth for what the site uses; where the
> two differ, the CSS wins. The values deliberately differ in these places:
>
> | Layout | Role | Here | In the CSS | Why |
> |---|---|---|---|---|
> | Basketball | link, accent | #8FB0FF | #9AB1DC | derived from the league colour (`league-tint`) |
> | Basketball | next-game panel | #1A2B6B | #022274 | the league colour darkened, so a league's own colour works |
> | Basketball | teams | five colours | six: a magenta (#F27AB0 dark) is added | six slots in every layout |
> | Classic | accent, rank 1 chip, link | #9DB6E8 | #AAB6CC | derived (`league-tint`) |
> | Classic | stolen-end text, tint | #FF8A9A on #4A1622 | #DA9B9C on #510915 | derived from the layout accent |
> | Curling | accent | #8CB8E8 | #9DB2CE | derived (`league-tint`) |
> | Curling | stolen-end text, tint, line | #FF8A9A, #4A1622, #A23A4E | #EB8D8A, #53030D, #D85154 | derived; the frame must reach 3:1 |
> | Hockey | centre-line red (`hot`) | #FF6B7A | #FF7482 | 4.5:1 on the shaded rows (was 4.45) |
> | Slo-pitch | header, next-game panel | #1E4527, #1A3D22 | #1D4624, #183E1F | derived from the league green |
> | Scoreboard | header, links | green #2B7539, #6FCF7F | red #CF2528, #F2A39A | the default league colour is red; the mockup was drawn with slo-pitch's green |
> | Scoreboard | teams | basketball's five | the same five plus grey #C3CDD7 | six slots |
>
> The light-theme changes made for contrast are in the "Mockup colours changed for AA" section of
> [`design.md`](design.md). Contrast results for every pair are in [`contrast.md`](contrast.md).

Each layout's dark theme, as the mockups use it. Stage 3 turned these into the
layouts' CSS variables. Checked for AA contrast on the main pairs.

## Curling
- ground #0B1620 (pebble dots #CFE6FF0D); header/footer #060D15
- raised #13222F; line #24394B
- next-draw panel #16324F (border #2A4D70, rows #FFFFFF1F); sheet tiles #F2F6FA with #0B1620
- text #E8F0F6; muted #9DB0C2 (on header/panel #C5D3E2)
- accent (links, numbers, table rule) #8CB8E8
- house: red #E5354F, blue #3D7CC9, white #F2F6FA
- stolen end: #FF8A9A on #4A1622 (border #A23A4E)
- teams: #E8475A, #34A464, #6FA3EA, #B391EE, #E9B940, #C3CDD7

## Classic (shown with curling's navy)
- ground #0B1220; raised (header, cards) #141D30; line #26324A; footer #060A14
- league colour lifted: nav bar #2A4A82 (edge #3A5C98); panel #1F3A68 (border #34548A, rows #FFFFFF1A)
- text #EEF2FA; muted #A0AAC0 (on navy #CDD6EA)
- accent #9DB6E8; rank 1 chip #9DB6E8 with #0B1220, others #22304D with #C9D6F2
- hammer marker ring #C9D6F2, dot #FF6B7D

## Hockey
- ground (slate ice) #17202B; raised #212C39; boards (header, footer, next-game panel) #090B0F
- line #334255; text #EEF2F7; muted #A3AEBD; link #8DB8FF
- centre-line red #FF6B7A (glow #FF4D5E); blue line #6FA8FF (glow #5C9BFF); kickplate #F2A900
- rank chip #2E3A4B with #EEF2F7 (rank 1 #F2A900 with #14181F)
- teams: #FF6B7A, #6FA8FF, #4FB164, #7FDDE6, #8E96A3, #F0965A

## Slo-pitch
- ground #131A14 (chalk rules rgba(244,236,214,.045)); raised #22201A
- header #1E4527; next-game panel #1A3D22 (inset #2F5E39); footer #0B0F0B
- line #3A362C; strong line #57503F; chalk rule #D9CFB6
- text #F4ECD9; muted #BDB29C
- green accent #86CC92 (border #6DB97A); clay #E0835A (arc #C4643C); 5-run mark #E8875E; floodlights #FFF4D6
- teams: #F27463, #A8825A, #6E98EA, #F0C04A, #B9A3F0, #5CC7C2

## Basketball (follows the live Masters site's dark theme)
- ground #0A1022; raised #131B34; line #243052
- text #EEF2FF; muted #9AA6C4; muted on header/footer and inactive tabs #B8C3E0 (#9AA6C4 is only ~4.4:1 on the night sky)
- accent #8FB0FF; active tab #FF5C66
- next-game panel #1A2B6B (text #B8CCFF, rows #FFFFFF14); footer #18214D (fine print #A9B6DA)
- header sky #0A1022 / #111A3E / #2C3A80 / #4F5EA8; hills #141C42 / #03060C; moon #E8ECF7
- teams: #5B9DF0, #3CC8C0, #FF9A52, #6CC46F, #B08CF0

## Scoreboard (shown with slo-pitch's green)
- ground #121212; raised #1A1A1A (outline #2A2A2A); rows #232323; scoreboard black #000000
- line #333333; strong rule #E8E8E8; text #F2F2F2; muted #A8A8A8
- digits #FFC233; losing score #8A8A8A; bar track #3A3A3A, fill #E8E8E8 (leader #FFC233)
- league green lifted #2B7539 (header text #FFFFFF / #E3EEDF); green text accent #6FCF7F
