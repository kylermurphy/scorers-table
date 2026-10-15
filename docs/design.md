# Designs

## Design canvases
- **scorers-table: layouts** (phone, light, and a dark Home for each layout):
  https://claude.ai/artifact/WUVtsLg2GDS5fVa8KzqJAN
  - an overview board: the six layouts' fonts and colours;
  - sport layouts: Home and Game for basketball, curling, hockey, slo-pitch;
  - general layouts: Classic (with curling, with hockey) and Scoreboard (with
    slo-pitch, with basketball);
  - dark: one Home per layout.
- **The Masters basketball site's directions** (where Classic, Scoreboard and
  the basketball layout come from): https://claude.ai/artifact/BaXVw5DEwLEePb3chLk3c5

The canvases are private to their owner until shared from their Share menu.

## The six layouts

| Layout | Kind | Type | Colours (light) |
|---|---|---|---|
| Basketball | sport | Barlow Condensed + Barlow | deep blue #032F98 header with a sunrise edge, coral #FF5C66 active tab, ink #0B1B3F, page #F4F6FB |
| Curling | sport | Alegreya + Source Sans 3 | pebbled ice #EEF4F8, navy ink #0E2233, house red #C8102E and blue #1D4E89 |
| Hockey | sport | Saira Condensed + Saira | white ice, boards #14181F, red #C8102E and blue #1D4E89 lines, kickplate #F2A900 |
| Slo-pitch | sport | Zilla Slab + Work Sans | scorebook paper #FBF7EE, clay #B5532E, outfield green #2F6B3A, ink #22201C |
| Classic | general | Barlow Condensed + Barlow | white header, one bar in the league's colour, page #F4F6FB |
| Scoreboard | general | Anton + Chakra Petch | black #111111, amber digits #FFC233, header bar in the league's colour |

Dark palettes: [`dark-palettes.md`](dark-palettes.md).

## Decisions so far
- Every layout has light and dark; dark is a colour swap, never a different
  structure.
- One shared desktop grid for all layouts (header on one row, main column of
  about two thirds, side column); layouts only re-skin it. Desktop comes late
  (stage 9).
- Sample leagues are made up: Riverside Masters Basketball, Pine Lake Curling
  Club, Northside Old-Timers Hockey, Maple Park Slo-Pitch.
- The mockups are for reference: rebuild them as clean templates and CSS
  variables; don't copy their inline styles.
