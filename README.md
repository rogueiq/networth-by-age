# Net Worth by Age Checker (@rogueiq)

A one-page website. You type your age (or pick an age group) and your net worth, and it shows
where you stand against US families your age, using the Federal Reserve's
**2025 Survey of Consumer Finances (SCF)**. All dollar figures are in **2025 dollars**.

Everything runs inside your browser. Nothing you type is sent or saved anywhere.
For education only, not financial advice.

## What each file does

| File | What it is | Plain-English job |
|---|---|---|
| `index.html` | HTML | The page's content and layout: headings, the form, empty boxes for results, the footer. Think of it as the skeleton. |
| `style.css` | CSS | How it looks: black background, white text, the green accent, spacing, phone vs. desktop layout. Change `--accent` at the top to change the brand color everywhere. |
| `app.js` | JavaScript | What it does: reads your inputs, finds your age group, works out your percentile, fills in the results, and draws the chart. |
| `data.js` | JavaScript (data only) | Every number the page shows, with comments explaining exactly where each one came from. If the Fed releases a new survey, this is the only file to update. |
| `scripts/build_filters.py` | Python (not part of the site) | Recomputes the "Compare against" numbers in `data.js` from the Fed's public file, after checking that its method matches the Fed's official Table 4. Only needed if the data changes. |
| `screenshots/` | Images | Test pictures of the page at phone width (390px) and desktop width (1280px). Not needed by the site. |
| `README.md` | Notes | This file. GitHub shows it on the repo's front page. |

The browser loads `index.html` first. That file pulls in `style.css`, then `data.js`, then `app.js`.
Order matters: `app.js` uses the `SCF_DATA` and `SCF_FILTERS` defined in `data.js`.

## The "Compare against" filters

On top of age, you can compare against **one** extra group at a time (no stacking, because
stacked groups get too small to trust):

| Filter | Choices | Age groups used |
|---|---|---|
| Couple vs. single | Couple (married or living with a partner) / Single | Normal 10-year groups |
| Kids vs. no kids | Have kids / No kids | Under 45 / 45–64 / 65+ |
| Number of kids | 0 / 1 / 2 / 3+ | Under 55 only (one group) |
| Homeowner vs. renter | Own / Rent or other | 10-year groups; renters 65+ are combined |
| Education | High school or less / Some college or associate / Bachelor's or higher | 10-year groups |
| Household income | 5 groups by 2024 income: under $35,000, $35,000–$61,999, $62,000–$99,999, $100,000–$169,999, $170,000+ | Under 45 / 45–64 / 65+ |
| Work status | Employee / Self-employed / Retired | Under 45 / 45–64 / 65+ (retired under 45 isn't available) |

**Why the age groups change.** The survey talks to about 4,400 families. Split them by age *and* another
trait and some groups get small. Each group (a "cell") stores `n`, the number of survey families in it.
The rule in `app.js`:

1. Use the filter's normal age grouping.
2. If that cell has fewer than 100 families, widen the age group (10-year groups → 3 groups → 2 groups)
   and tell the user in plain words.
3. If it's still under 100, grey the choice out with a "not enough survey data" note.

Filtered views also show less detail on purpose: the median, 25th and 75th percentiles, plus the 10th and
90th only when the group has at least 200 families. No mean (too easily moved by one very rich family),
no 95th or 99th, and your rank is rounded to the nearest 5.

**Income** is 2024 income before taxes, because the 2025 survey asks about the previous year. The income
group edges come from the same public file (the Fed's 20th/40th/60th/80th income percentiles, converted
back from 2025 dollars to the 2024 dollars people actually earned).

**Footnotes.** Where the Fed publishes its own all-ages median and mean for a group (homeowners, renters,
education, income groups, work status), the result shows it as a footnote. The Fed doesn't publish
anything split by age *and* these traits, so the age-by-group numbers are computed by us from its public data.

## Where the numbers come from

- **Median and mean by age:** Fed's historical tables built from the public data, Table 4, 2025 columns.
  <https://www.federalreserve.gov/econres/files/scf2025_tables_public_real_historical.xlsx>
- **Percentiles (1st–99th) by age:** the Fed doesn't publish these by age, so they were computed from the
  Fed's own public data file (2025 SCF Summary Extract, `NETWORTH` weighted by `WGT`, grouped by `AGECL`).
  The same method reproduces every median and mean in Table 4 to the nearest $10.
  <https://www.federalreserve.gov/econres/files/scfp2025excel.zip>
- **Filter numbers:** same Summary Extract file, same method. `scripts/build_filters.py` shows exactly how.
- **Footnote figures:** the Fed's summary report, Table 2 (full internal data, so slightly different):
  <https://www.federalreserve.gov/publications/files/scf26.pdf>
- All SCF files: <https://www.federalreserve.gov/econres/scfindex.htm>

## Try it on your computer

You need a tiny local web server (opening the file directly mostly works too, but a server is closer to the real thing).
In a terminal, inside this folder:

```
python3 -m http.server 8000
```

Then open <http://localhost:8000> in your browser. Press `Ctrl+C` in the terminal to stop it.

## How GitHub Pages will serve it

GitHub Pages is free hosting for plain websites like this one. There's no build step and no server code.
GitHub just hands these files to visitors' browsers as they are.

1. Create a repository on GitHub (for example `networth-by-age`) and upload these files to it, with `index.html` at the top level.
2. In the repo, go to **Settings → Pages**. Under "Build and deployment", choose **Deploy from a branch**, pick the `main` branch and the `/ (root)` folder, then save.
3. After a minute, the site is live at `https://YOUR-USERNAME.github.io/networth-by-age/`.
   GitHub serves `index.html` automatically when someone visits that address.
4. Every time a change is pushed to `main`, GitHub republishes the site on its own.
5. Later, a custom domain (like `rogueiq.com`) can be added in the same **Settings → Pages** screen.

## Not done yet

- The "Get the weekly breakdown" email signup is a **placeholder**. It sends nothing and only shows a "coming soon" note.
  To make it real, it would be connected to a newsletter service such as beehiiv or Substack.
