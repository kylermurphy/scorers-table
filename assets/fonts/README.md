# Self-hosted fonts

Web fonts for the six layouts, served from this repository so a league's site
makes no request to Google at runtime. Declared in [`../css/fonts.css`](../css/fonts.css).

All files are WOFF2, Latin subset only (Basic Latin, Latin-1, Latin Extended
bits such as dotless i and oe, general punctuation U+2000-206F, euro, trademark,
minus). That covers accented names such as "André". Variable fonts are used
where Google serves one for the family (one file, weight range declared in
`@font-face`); otherwise there is one static file per weight.

Licence for every file: SIL Open Font License 1.1 (OFL). The licence text for
each family is in [`licenses/`](licenses/), copied from
`https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/OFL.txt`.

| File | Family | Weight | Size (bytes) | Source | Licence |
|---|---|---|---:|---|---|
| `barlow-400.woff2` | Barlow | 400 | 22,196 | <https://fonts.gstatic.com/s/barlow/v13/7cHpv4kjgoGqM7E_DMs5.woff2> | SIL OFL 1.1 |
| `barlow-500.woff2` | Barlow | 500 | 22,008 | <https://fonts.gstatic.com/s/barlow/v13/7cHqv4kjgoGqM7E3_-gs51os.woff2> | SIL OFL 1.1 |
| `barlow-600.woff2` | Barlow | 600 | 22,772 | <https://fonts.gstatic.com/s/barlow/v13/7cHqv4kjgoGqM7E30-8s51os.woff2> | SIL OFL 1.1 |
| `barlow-700.woff2` | Barlow | 700 | 22,788 | <https://fonts.gstatic.com/s/barlow/v13/7cHqv4kjgoGqM7E3t-4s51os.woff2> | SIL OFL 1.1 |
| `barlowcondensed-600.woff2` | Barlow Condensed | 600 | 22,308 | <https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B4873z3bWuQ.woff2> | SIL OFL 1.1 |
| `barlowcondensed-700.woff2` | Barlow Condensed | 700 | 22,444 | <https://fonts.gstatic.com/s/barlowcondensed/v13/HTxwL3I-JCGChYJ8VI-L6OO_au7B46r2z3bWuQ.woff2> | SIL OFL 1.1 |
| `alegreya-variable.woff2` | Alegreya | 700 to 800 | 43,476 | <https://fonts.gstatic.com/s/alegreya/v41/4UaBrEBBsBhlBjvfkSLhx6g.woff2> | SIL OFL 1.1 |
| `sourcesans3-variable.woff2` | Source Sans 3 | 400 to 700 | 28,872 | <https://fonts.gstatic.com/s/sourcesans3/v20/nwpStKy2OAdR1K-IwhWudF-R3w8aZQ.woff2> | SIL OFL 1.1 |
| `sairacondensed-600.woff2` | Saira Condensed | 600 | 17,980 | <https://fonts.gstatic.com/s/sairacondensed/v12/EJRLQgErUN8XuHNEtX81i9TmEkrnfc9Q962f.woff2> | SIL OFL 1.1 |
| `sairacondensed-700.woff2` | Saira Condensed | 700 | 17,808 | <https://fonts.gstatic.com/s/sairacondensed/v12/EJRLQgErUN8XuHNEtX81i9TmEkrnGc5Q962f.woff2> | SIL OFL 1.1 |
| `sairacondensed-800.woff2` | Saira Condensed | 800 | 17,984 | <https://fonts.gstatic.com/s/sairacondensed/v12/EJRLQgErUN8XuHNEtX81i9TmEkrnBc1Q962f.woff2> | SIL OFL 1.1 |
| `saira-variable.woff2` | Saira | 400 to 700 | 32,888 | <https://fonts.gstatic.com/s/saira/v23/memjYa2wxmKQyPMrZX79wwYZQMhsyuSLiIvS.woff2> | SIL OFL 1.1 |
| `zillaslab-600.woff2` | Zilla Slab | 600 | 26,472 | <https://fonts.gstatic.com/s/zillaslab/v12/dFa5ZfeM_74wlPZtksIFYuUe6HOpWw.woff2> | SIL OFL 1.1 |
| `zillaslab-700.woff2` | Zilla Slab | 700 | 26,100 | <https://fonts.gstatic.com/s/zillaslab/v12/dFa5ZfeM_74wlPZtksIFYoEf6HOpWw.woff2> | SIL OFL 1.1 |
| `worksans-variable.woff2` | Work Sans | 400 to 700 | 50,316 | <https://fonts.gstatic.com/s/worksans/v24/QGYsz_wNahGAdqQ43Rh_fKDp.woff2> | SIL OFL 1.1 |
| `anton-400.woff2` | Anton | 400 | 18,612 | <https://fonts.gstatic.com/s/anton/v27/1Ptgg87LROyAm3Kz-C8.woff2> | SIL OFL 1.1 |
| `chakrapetch-500.woff2` | Chakra Petch | 500 | 9,956 | <https://fonts.gstatic.com/s/chakrapetch/v13/cIflMapbsEk7TDLdtEz1BwkebIl1R5_F.woff2> | SIL OFL 1.1 |
| `chakrapetch-600.woff2` | Chakra Petch | 600 | 9,968 | <https://fonts.gstatic.com/s/chakrapetch/v13/cIflMapbsEk7TDLdtEz1BwkeQI51R5_F.woff2> | SIL OFL 1.1 |
| `chakrapetch-700.woff2` | Chakra Petch | 700 | 9,900 | <https://fonts.gstatic.com/s/chakrapetch/v13/cIflMapbsEk7TDLdtEz1BwkeJI91R5_F.woff2> | SIL OFL 1.1 |

Total: 19 files, 444,848 bytes (434 KiB).

## What a visitor downloads

`fonts.css` declares every face, but browsers fetch an `@font-face` file only
when text on the page actually uses that family and weight. A league's page
therefore downloads only the faces its layout uses (for example, about
131 KiB for the Barlow layout), not the whole 434 KiB set.

## How to re-fetch

The woff2 URLs are versioned (`/v13/`), so they are stable. To update, ask
Google's CSS API for each family with a modern browser user agent (it then
returns woff2 files split by `unicode-range`), and download the block marked
`/* latin */`:

```sh
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
curl -sS -A "$UA" "https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&display=swap"
# variable families: use a range, e.g. family=Saira:wght@400..700
```

Families requested: Barlow 400;500;600;700, Barlow Condensed 600;700, Alegreya
700..800, Source Sans 3 400..700, Saira Condensed 600;700;800, Saira 400..700,
Zilla Slab 600;700, Work Sans 400..700, Anton 400, Chakra Petch 500;600;700.
After downloading, keep `fonts.css` in step (file names, weights) and check that
each file starts with the bytes `wOF2`.
