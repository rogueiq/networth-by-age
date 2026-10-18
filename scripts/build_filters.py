"""
build_filters.py: recomputes the filter numbers in data.js from the Fed's public file.

You don't need this to run the website. It's here so anyone can check, or redo,
how the filtered numbers were made.

How to run it:
  1. Download https://www.federalreserve.gov/econres/files/scfp2025excel.zip and unzip it.
     You get SCFP2025.csv (the Fed's 2025 SCF Summary Extract, about 21 MB).
  2. pip install pandas numpy
  3. python3 scripts/build_filters.py /path/to/SCFP2025.csv
It rewrites everything in data.js below the line "// ===== FILTERS (generated".

Method (same as the Fed's own published tables from this file):
  - All 5 "implicates" (5 copies of each family with different filled-in answers)
    are pooled, each row weighted by WGT.
  - A percentile is the first net worth value where the cumulative weight share
    reaches that percentile.
  - n (sample size) = rows in the cell / 5, i.e. the number of survey families.
"""
import sys, json, re
import numpy as np
import pandas as pd

CSV = sys.argv[1] if len(sys.argv) > 1 else "/workspace/scfdata/SCFP2025.csv"
DATA_JS = __file__.rsplit("/scripts/", 1)[0] + "/data.js"
MIN_N = 100        # below this a cell is "too thin" to show
FULL_RANGE_N = 200 # 10th and 90th percentiles shown only at or above this

df = pd.read_csv(CSV, usecols=["YY1", "WGT", "AGE", "AGECL", "MARRIED", "KIDS",
                               "EDCL", "HOUSECL", "INCCAT", "OCCAT1", "INCOME", "NETWORTH"])

def wq(values, weights, qs):
    """Weighted percentiles, pooled across implicates (the Fed's method)."""
    order = np.argsort(values, kind="stable")
    v, w = values[order], weights[order]
    cum = np.cumsum(w) / w.sum()
    return [float(v[np.searchsorted(cum, q)]) for q in qs]

def wmedian_mean(sub):
    return wq(sub.NETWORTH.values, sub.WGT.values, [0.5])[0], float(np.average(sub.NETWORTH, weights=sub.WGT))

# ---- Method check: our all-ages numbers must match the Fed's public Table 4 (thousands of 2025 $) ----
TABLE4 = {  # (mask, official median, official mean)
    "Owner": (df.HOUSECL == 1, 459.0, 1798.41),
    "Renter or other": (df.HOUSECL == 2, 10.55, 153.53),
    "No high school diploma": (df.EDCL == 1, 18.7, 293.88),
    "High school diploma": (df.EDCL == 2, 106.71, 470.03),
    "Some college": (df.EDCL == 3, 181.5, 661.35),
    "College degree": (df.EDCL == 4, 505.03, 2240.46),
    "Income less than 20": (df.INCCAT == 1, 12.84, 145.33),
    "Income 20-39.9": (df.INCCAT == 2, 80.0, 254.58),
    "Income 40-59.9": (df.INCCAT == 3, 203.1, 462.27),
    "Income 60-79.9": (df.INCCAT == 4, 385.5, 803.49),
    "Income 80-89.9": (df.INCCAT == 5, 818.0, 1421.45),
    "Income 90-100": (df.INCCAT == 6, 3624.6, 7565.79),
    "Working for someone else": (df.OCCAT1 == 1, 156.0, 681.17),
    "Self-employed": (df.OCCAT1 == 2, 575.1, 3469.98),
    "Retired": (df.OCCAT1 == 3, 380.9, 1485.52),
}
for name, (mask, med, mean) in TABLE4.items():
    m, a = wmedian_mean(df[mask])
    assert abs(m / 1e3 - med) < 0.006 and abs(a / 1e3 - mean) < 0.006, (name, m, a, med, mean)
print("Method check passed: all-ages medians and means match Fed Table 4 for", len(TABLE4), "groups")

# ---- Age groupings ----
LEVELS = {
    6: [("under35", "under 35", 18, 34), ("35-44", "35–44", 35, 44), ("45-54", "45–54", 45, 54),
        ("55-64", "55–64", 55, 64), ("65-74", "65–74", 65, 74), ("75plus", "75 and older", 75, None)],
    3: [("under45", "under 45", 18, 44), ("45-64", "45–64", 45, 64), ("65plus", "65 and older", 65, None)],
    2: [("under55", "under 55", 18, 54), ("55plus", "55 and older", 55, None)],
}

def in_band(age, lo, hi):
    return (age >= lo) & ((age <= hi) if hi is not None else True)

# ---- Filters (membership rules use the Fed's own summary variables) ----
K = df.KIDS
FILTERS = [
    dict(id="household", label="Couple vs. single", startLevel=6, options=[
        dict(id="couple", label="Couple", phrase="who are married or living with a partner", mask=df.MARRIED == 1),
        dict(id="single", label="Single", phrase="who are single (not married or living with a partner)", mask=df.MARRIED == 2)]),
    dict(id="kids", label="Kids vs. no kids", startLevel=3, options=[
        dict(id="kids", label="Have kids", phrase="with kids in the household", mask=K > 0),
        dict(id="nokids", label="No kids", phrase="with no kids in the household", mask=K == 0)]),
    dict(id="kidcount", label="Number of kids (under 55 only)", startLevel=2, allowedAge6=["under35", "35-44", "45-54"], options=[
        dict(id="k0", label="0 kids", phrase="with no kids in the household", mask=K == 0),
        dict(id="k1", label="1 kid", phrase="with 1 kid in the household", mask=K == 1),
        dict(id="k2", label="2 kids", phrase="with 2 kids in the household", mask=K == 2),
        dict(id="k3", label="3+ kids", phrase="with 3 or more kids in the household", mask=K >= 3)]),
    dict(id="home", label="Homeowner vs. renter", startLevel=6, options=[
        dict(id="owner", label="Own my home", phrase="who own their home", mask=df.HOUSECL == 1,
             official=[["Homeowners, all ages", 459000, 1798410]]),
        dict(id="renter", label="Rent / other", phrase="who rent or have another living arrangement", mask=df.HOUSECL == 2,
             forceLevel={"65-74": 3, "75plus": 3},
             forceNote="Renters aged 65 and older are combined into one group because the survey has few of them.",
             official=[["Renters or other, all ages", 10550, 153530]])]),
    dict(id="education", label="Education", startLevel=6, options=[
        dict(id="hs", label="High school or less", phrase="whose head has a high school diploma or less", mask=df.EDCL.isin([1, 2]),
             official=[["No high school diploma, all ages", 18700, 293880], ["High school diploma, all ages", 106710, 470030]]),
        dict(id="somecollege", label="Some college / associate", phrase="whose head has some college or an associate degree", mask=df.EDCL == 3,
             official=[["Some college, all ages", 181500, 661350]]),
        dict(id="bachelor", label="Bachelor's or higher", phrase="whose head has a bachelor's degree or higher", mask=df.EDCL == 4,
             official=[["College degree, all ages", 505030, 2240460]])]),
    dict(id="income", label="Household income", startLevel=3, input="income", options=[
        dict(id="inc1", label="Bottom 20%", phrase="in the bottom 20% of household income", mask=df.INCCAT == 1,
             official=[["Income below 20th percentile, all ages", 12840, 145330]]),
        dict(id="inc2", label="20th–40th percentile", phrase="in the 20th–40th percentile of household income", mask=df.INCCAT == 2,
             official=[["Income 20th–39.9th percentile, all ages", 80000, 254580]]),
        dict(id="inc3", label="40th–60th percentile", phrase="in the 40th–60th percentile of household income", mask=df.INCCAT == 3,
             official=[["Income 40th–59.9th percentile, all ages", 203100, 462270]]),
        dict(id="inc4", label="60th–80th percentile", phrase="in the 60th–80th percentile of household income", mask=df.INCCAT == 4,
             official=[["Income 60th–79.9th percentile, all ages", 385500, 803490]]),
        dict(id="inc5", label="Top 20%", phrase="in the top 20% of household income", mask=df.INCCAT >= 5,
             official=[["Income 80th–89.9th percentile, all ages", 818000, 1421450], ["Income 90th–100th percentile, all ages", 3624600, 7565790]])]),
    dict(id="work", label="Work status", startLevel=3, options=[
        dict(id="employee", label="Employee", phrase="whose head works for someone else", mask=df.OCCAT1 == 1,
             official=[["Working for someone else, all ages", 156000, 681170]]),
        dict(id="selfemployed", label="Self-employed", phrase="whose head is self-employed or a business partner", mask=df.OCCAT1 == 2,
             official=[["Self-employed, all ages", 575100, 3469980]]),
        dict(id="retired", label="Retired", phrase="whose head is retired", mask=df.OCCAT1 == 3,
             official=[["Retired, all ages", 380900, 1485520]])]),
]

# Income cut-offs. INCOME in the file is 2024 income converted to 2025 dollars by the Fed
# (factor 4750/4625 from its macro). The user types 2024 dollars, so convert back.
CPILAG = 4750 / 4625
inc_min = df.groupby("INCCAT").INCOME.min()
cut_2025 = [float(inc_min[c]) for c in (2, 3, 4, 5)]          # lower bound of groups 2,3,4,5(+6)
check = wq(df.INCOME.values, df.WGT.values, [0.2, 0.4, 0.6, 0.8])
assert all(abs(a - b) < 1 for a, b in zip(cut_2025, check)), (cut_2025, check)
cut_2024 = [int(round(c / CPILAG)) for c in cut_2025]
print("Income cut-offs (2024 dollars):", cut_2024)

qs = [i / 100 for i in range(1, 100)]
out_filters = []
for f in FILTERS:
    of = {k: v for k, v in f.items() if k != "options"}
    of["options"] = []
    for o in f["options"]:
        oo = {k: v for k, v in o.items() if k != "mask"}
        cells = {}
        for level, bands in LEVELS.items():
            for bid, blabel, lo, hi in bands:
                sub = df[o["mask"] & in_band(df.AGE, lo, hi)]
                n = int(round(len(sub) / 5))
                cell = {"n": n}
                # Percentiles only for cells we might actually show (enough families,
                # and at or wider than the filter's starting age grouping).
                if n >= MIN_N and level <= f["startLevel"]:
                    p = wq(sub.NETWORTH.values, sub.WGT.values, qs)
                    cell["p"] = [int(round(v, -1)) for v in p]
                cells[f"{level}:{bid}"] = cell
        oo["cells"] = cells
        of["options"].append(oo)
    out_filters.append(of)

payload = {
    "minN": MIN_N,
    "fullRangeN": FULL_RANGE_N,
    "levels": {str(k): [{"id": b[0], "label": b[1], "minAge": b[2], "maxAge": b[3]} for b in v] for k, v in LEVELS.items()},
    "incomeCutoffs2024": cut_2024,
    "filters": out_filters,
}

# Write compact but readable JS: one line per cell.
js = json.dumps(payload, indent=2, ensure_ascii=False)
js = re.sub(r'\[\s+(-?\d+(?:,\s+-?\d+)*)\s+\]', lambda m: "[" + ",".join(m.group(1).split()).replace(",,", ",") + "]", js)
js = re.sub(r'\{\s+"n": (\d+)\s+\}', r'{ "n": \1 }', js)
js = re.sub(r'\{\s+"n": (\d+),\s+"p": (\[[^\]]*\])\s+\}', r'{ "n": \1, "p": \2 }', js)

header = """// ===== FILTERS (generated by scripts/build_filters.py; do not edit by hand) =====
/*
  SCF_FILTERS: numbers for the "Compare against" filters.
  Source: the Fed's 2025 SCF Summary Extract (public data, 2025 dollars):
    https://www.federalreserve.gov/econres/files/scfp2025excel.zip
  The Fed does NOT publish these age-by-group numbers; we computed them with the same
  method that reproduces the Fed's public Table 4 (the script checks this before writing).

  levels:  the three ways of grouping ages. 6 = the normal 10-year groups,
           3 = under 45 / 45–64 / 65+, 2 = under 55 / 55+.
  cells:   one entry per option and age group, keyed "level:ageGroupId".
           n = number of survey families in that cell (unweighted).
           p = net worth at the 1st..99th percentile (only stored when n >= minN).
  official: the Fed's own ALL-AGES median and mean for that group (public Table 4),
           shown as a footnote.
  incomeCutoffs2024: lower edges of the 20th/40th/60th/80th income percentiles,
           in 2024 dollars (the survey asks about 2024 income).
*/
const SCF_FILTERS = """

src = open(DATA_JS).read()
marker = "// ===== FILTERS (generated"
base = src.split(marker)[0].rstrip() + "\n\n"
open(DATA_JS, "w").write(base + header + js + ";\n")
print("Wrote", DATA_JS)
