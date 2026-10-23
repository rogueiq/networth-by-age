"""
build_page.py: writes the server-rendered tables, FAQ, JSON-LD, CSV and per-age pages.

Run it after changing data.js:   python3 scripts/build_page.py
deploy.sh in rogueiq-site runs it before every deploy, so the page always matches data.js
(the same file the API uses).

Two kinds of numbers:
  FED  = copied from the Fed report "Changes in U.S. Family Finances from 2022 to 2025"
         (scf26.pdf, Oct 2026), Table 2, thousands of 2025 dollars. Checked by hand.
  data.js percentiles = computed by RogueIQ from the 2025 SCF Summary Extract
         (all 5 implicates pooled, weighted by WGT). See build_filters.py for the method.
"""
import json, os, re, subprocess, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://rogueiq.com"
URL = SITE + "/net-worth-by-age/"
UPDATED = "2026-10-22"
UPDATED_TXT = "Oct 22, 2026"
RELEASED = "2026-10-09"

# Fed report Table 2 (thousands of 2025 dollars): (median2022, median2025, mean2022, mean2025, pct med, pct mean)
FED = {
    "under35": (42.7, 33.0, 200.8, 135.4, -23, -33),
    "35-44": (148.4, 155.6, 601.5, 681.9, 5, 13),
    "45-54": (270.6, 253.7, 1067.9, 1244.5, -6, 17),
    "55-64": (398.9, 411.9, 1714.7, 1878.0, 3, 10),
    "65-74": (448.6, 431.3, 1963.9, 1897.6, -4, -3),
    "75plus": (367.3, 504.9, 1777.4, 1962.2, 37, 10),
    "all": (211.1, 215.9, 1164.1, 1241.5, 2, 7),
}
# Families in the public Summary Extract per age group (rows / 5), counted by RogueIQ.
N_EXTRACT = {"under35": 628, "35-44": 779, "45-54": 832, "55-64": 841, "65-74": 776, "75plus": 504}
SLUG = {"under35": "under-35", "35-44": "35-44", "45-54": "45-54", "55-64": "55-64", "65-74": "65-74", "75plus": "75-and-older"}
LONG = {"under35": "under 35", "35-44": "aged 35–44", "45-54": "aged 45–54", "55-64": "aged 55–64",
        "65-74": "aged 65–74", "75plus": "75 and older"}

js = subprocess.run(["node", "-e", "eval(require('fs').readFileSync(process.argv[1],'utf8')+';process.stdout.write(JSON.stringify(SCF_DATA))')",
                     os.path.join(ROOT, "data.js")], capture_output=True, text=True, check=True).stdout
DATA = json.loads(js)
BR = DATA["brackets"]
for b in BR:
    assert FED[b["id"]][1] * 1000 == b["reportMedian"] and FED[b["id"]][3] * 1000 == b["reportMean"], b["id"]
P = lambda b, q: b["percentiles"][q - 1]

def k(v):  # thousands -> "$215,900"
    return "${:,.0f}".format(v * 1000)
def d(v):
    return ("−$" if v < 0 else "$") + "{:,.0f}".format(abs(v))
def pc(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + f"{abs(v)}%"
def m(v):
    return "${:.2f}M".format(v / 1e6)
e = html.escape
SRC_R = 'Source: Federal Reserve, 2025 SCF, report Table 2 (released Oct 9, 2026). 2025 dollars.'
SRC_X = 'Source: computed by RogueIQ from the Federal Reserve’s 2025 SCF Summary Extract, survey-weighted. 2025 dollars.'
FED_LINKS = [
    ("Fed SCF index", "https://www.federalreserve.gov/econres/scfindex.htm"),
    ("Report PDF (scf26.pdf)", "https://www.federalreserve.gov/publications/files/scf26.pdf"),
    ("Historical tables, public data (xlsx)", "https://www.federalreserve.gov/econres/files/scf2025_tables_public_real_historical.xlsx"),
    ("Summary Extract (zip)", "https://www.federalreserve.gov/econres/files/scfp2025excel.zip"),
]
by = {b["id"]: b for b in BR}
u35, a75 = by["under35"], by["75plus"]

# ---------- FAQ (visible text == JSON-LD text) ----------
FAQ = [
    ("What is the median net worth by age in 2025?",
     "Median family net worth in 2025 was " + "; ".join(f"{k(FED[b['id']][1])} {'under 35' if b['id']=='under35' else 'at ' + b['label'] if b['id']!='75plus' else 'at 75 and older'}" for b in BR) + ".",
     SRC_R),
    ("What is the average net worth by age?",
     f"Mean (average) family net worth ranged from {k(FED['under35'][3])} under 35 to {k(FED['75plus'][3])} at 75 and older in 2025. Means sit far above medians because a small number of very wealthy families pull the average up.",
     SRC_R),
    ("What net worth puts you in the top 1% for your age?",
     f"RogueIQ’s calculation puts the 99th percentile at about {m(P(u35,99))} for families under 35, {m(P(by['35-44'],99))} at 35–44 and {m(P(by['45-54'],99))} at 45–54. These estimates rest on few survey families, so treat them as rough.",
     SRC_X),
    ("What net worth is top 10% for my age?",
     f"The 90th percentile ranges from {d(P(u35,90))} for families under 35 to {d(P(a75,90))} for families 75 and older, by RogueIQ’s calculation.",
     SRC_X),
    ("Is my net worth good for my age?",
     "The survey can only show where a number ranks, and it can’t judge anyone’s finances. For example, $150,000 at age 35 is about the 49th percentile of families aged 35–44. Educational, not advice.",
     "Source: RogueIQ net worth API (computed from the 2025 SCF Summary Extract)."),
    ("Did net worth go up from 2022 to 2025?",
     f"Median family net worth rose 2% to {k(FED['all'][1])} and the mean rose 7% to {k(FED['all'][3])}, in 2025 dollars. The under-35 median fell 23% while the 75-and-older median rose 37%.",
     SRC_R),
    ("Is net worth measured by household or by individual?",
     "By family. The SCF’s “family” is close to the Census Bureau’s “household,” and families are grouped by the age of a designated reference person.",
     "Source: Federal Reserve, 2025 SCF report, Appendix A."),
    ("When will the next update come out?",
     "The SCF is conducted every three years, so the next survey would be the 2028 SCF. If the usual schedule holds, its results would come out around 2029.",
     "Source: Federal Reserve, 2025 SCF report (triennial survey). Timing is an expectation."),
]

def table(head, rows, cls="cuts data"):
    t = f'<div class="tablewrap"><table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
    for r in rows:
        t += "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
    return t + "</tbody></table></div>"

# ---------- head ----------
TITLE = "Net Worth by Age 2025: Median, Average & Percentiles | RogueIQ"
DESC = "Median net worth by age from the Fed's 2025 SCF (released Oct 9, 2026), with 25th–99th percentiles. Check where you stand privately in your browser."

def graph(url, faq=True, extra_crumb=None):
    org = {"@type": "Organization", "@id": SITE + "/#org", "name": "RogueIQ", "url": SITE + "/"}
    g = [
        {"@type": "WebApplication", "@id": URL + "#app", "name": "Net Worth by Age Checker", "url": URL,
         "applicationCategory": "FinanceApplication", "operatingSystem": "Any (web browser)", "browserRequirements": "Requires JavaScript",
         "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "publisher": org, "isBasedOn": {"@id": URL + "#data"}, "dateModified": UPDATED},
        {"@type": "Dataset", "@id": URL + "#data", "name": "U.S. family net worth by age: medians, means and percentiles (2025 SCF)",
         "description": "Median and mean net worth by age of reference person from the Federal Reserve's 2025 Survey of Consumer Finances, plus weighted percentiles computed by RogueIQ from the public Summary Extract. 2025 dollars.",
         "url": URL, "temporalCoverage": "2025", "spatialCoverage": {"@type": "Place", "name": "United States"},
         "variableMeasured": ["Median net worth", "Mean net worth", "Net worth percentiles (p25, p50, p75, p90, p99)"],
         "creator": [{"@type": "Organization", "name": "Board of Governors of the Federal Reserve System", "url": "https://www.federalreserve.gov/econres/scfindex.htm"}, {"@id": SITE + "/#org"}],
         "isBasedOn": "https://www.federalreserve.gov/econres/files/scfp2025excel.zip",
         "creditText": "Board of Governors of the Federal Reserve System, 2025 Survey of Consumer Finances; percentiles computed by RogueIQ.",
         "datePublished": RELEASED, "dateModified": UPDATED,
         "distribution": [
             {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": URL + "api/v1/networth-by-age?age=35&net_worth=150000"},
             {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": URL + "networth-by-age-2025.csv"}]},
    ]
    if faq:
        g.append({"@type": "FAQPage", "@id": URL + "#faq", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a, _ in FAQ]})
    crumbs = [("RogueIQ", SITE + "/"), ("Net worth by age", URL)] + ([extra_crumb] if extra_crumb else [])
    g.append({"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]})
    return json.dumps({"@context": "https://schema.org", "@graph": g}, ensure_ascii=False).replace("</", "<\\/")

def head(title, desc, url, ld):
    return f'''  <title>{e(title)}</title>
  <meta name="description" content="{e(desc)}">
  <link rel="canonical" href="{url}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="RogueIQ">
  <meta property="og:title" content="{e(title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://rogueiq.com/wire/icons/icon-512.png">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:site" content="@rogueiq">
  <script type="application/ld+json">{ld}</script>'''

UPD = f'<p class="updated">Data: 2025 SCF, released <time datetime="{RELEASED}">Oct 9, 2026</time> · Page updated <time datetime="{UPDATED}">{UPDATED_TXT}</time></p>'
HERO = f'''    <section class="hero">
      <p class="eyebrow">Net worth by age</p>
      <h1>Net worth by age: where do you stand? (Fed 2025 data)</h1>
      <p class="lede">Median U.S. family net worth was {k(FED['all'][1])} in 2025, ranging from {k(FED['under35'][1])} for families under 35 to {k(FED['75plus'][1])} for families 75 and older, according to the Federal Reserve’s 2025 Survey of Consumer Finances (released Oct 9, 2026).</p>
      <p class="lede">Enter your age and net worth below to see your percentile. Nothing leaves your browser.</p>
      {UPD}
    </section>'''

def stat_p(t):
    return f'<p class="stat-line">{t}</p>'

def body():
    rows_a = [[b["label"], k(FED[b["id"]][1]), k(FED[b["id"]][3])] for b in BR] + [["<strong>All families</strong>", k(FED["all"][1]), k(FED["all"][3])]]
    rows_b = [[b["label"]] + [d(P(b, q)) for q in (25, 50, 75, 90, 99)] for b in BR]
    rows_g = [[b["label"], k(FED[b["id"]][1]), d(b["median"]), k(FED[b["id"]][3]), d(b["mean"])] for b in BR]
    rows_d = [[b["label"], f"{FED[b['id']][0]:,.1f}", f"{FED[b['id']][1]:,.1f}", pc(FED[b['id']][4]), f"{FED[b['id']][2]:,.1f}", f"{FED[b['id']][3]:,.1f}", pc(FED[b['id']][5])] for b in BR]
    f = FED["all"]; rows_d.append(["<strong>All families</strong>", f"{f[0]:,.1f}", f"{f[1]:,.1f}", pc(f[4]), f"{f[2]:,.1f}", f"{f[3]:,.1f}", pc(f[5])])
    faq = "".join(f'<div class="qa"><h3>{e(q)}</h3><p>{e(a)}</p><p class="src">{e(s)}</p></div>' for q, a, s in FAQ)
    brk = " · ".join(f'<a href="/net-worth-by-age/{SLUG[b["id"]]}/">Net worth {"under 35" if b["id"]=="under35" else "75 and older" if b["id"]=="75plus" else b["label"]}</a>' for b in BR)
    links = "".join(f'<li><a href="{u}" target="_blank" rel="noopener">{e(n)}</a></li>' for n, u in FED_LINKS)
    cite = ("RogueIQ (2026). Net worth by age, 2025 SCF. https://rogueiq.com/net-worth-by-age/ (accessed {date}). "
            "Data: Board of Governors of the Federal Reserve System, 2025 Survey of Consumer Finances (released Oct 9, 2026); "
            "percentiles computed by RogueIQ from the SCF Summary Extract.")
    return f'''    <section class="card prose" id="tables">
      <p class="links-top"><a href="/agents/#networth">Use this data from your AI agent (free MCP + API)</a> · <a href="#methodology">How we calculate percentiles</a></p>
      <h2 id="median-by-age">Median and mean net worth by age, 2025</h2>
      {stat_p(f"Median U.S. family net worth was {k(FED['all'][1])} in 2025 (Federal Reserve, 2025 SCF, released Oct 9, 2026).")}
      {table(["Age of reference person", "Median", "Mean"], rows_a)}
      <p class="src">{SRC_R}</p>
      {stat_p(f"Mean U.S. family net worth was {k(FED['all'][3])} in 2025, nearly six times the median (Federal Reserve, 2025 SCF).")}

      <h2 id="percentiles-by-age">Net worth percentiles by age, 2025 (computed by RogueIQ)</h2>
      <p>The Fed doesn’t publish percentiles by age. RogueIQ computed these from the Fed’s public Summary Extract using the survey weights; the live API returns the same numbers.</p>
      {table(["Age", "25th", "50th", "75th", "90th", "99th"], rows_b)}
      <p class="src">{SRC_X} Rounded to the nearest $10.</p>
      <p>These computed figures differ a little from the Fed’s report. The report uses the Fed’s final internal data, while the public extract is altered to protect respondents’ privacy (Fed report, Appendices A and B). RogueIQ’s computed medians and means match the Fed’s public-data historical tables (Table 4, 2025 columns, published to the nearest $10) for every age group and for all families. Where the report publishes a figure, use the report figure.</p>
      {table(["Age", "Fed median (report)", "RogueIQ median (extract)", "Fed mean (report)", "RogueIQ mean (extract)"], rows_g)}
      <p>The 99th percentile rests on few survey families (about 16 per imputed copy of the data for families under 35), and the SCF excludes people on the Forbes 400 list, so treat the top tail as rough.</p>
      <p class="links-top">By age group: {brk}</p>
    </section>

    <section class="card prose" id="what-counts">
      <h2>What counts in net worth</h2>
      <p>The Fed defines net worth as “the difference between families’ gross assets and their liabilities” (2025 SCF report, Table 2 note).</p>
      <ul>
        <li><strong>Financial assets:</strong> transaction accounts (checking, savings, money market), certificates of deposit, savings bonds, other bonds, stocks, pooled investment funds, retirement accounts (IRAs, Keogh accounts and employer accounts such as 401(k)s and 403(b)s), cash value life insurance, other managed assets, and other financial assets.</li>
        <li><strong>Nonfinancial assets:</strong> vehicles, the primary residence, other residential property, equity in nonresidential property, business equity, and other items such as precious metals, art and collections.</li>
        <li><strong>Minus debts:</strong> mortgages and home equity lines of credit secured by the primary residence, other lines of credit, installment loans (education, vehicle and other), credit card balances, and other debt. Debt on businesses and nonresidential real estate is netted against those assets.</li>
      </ul>
      <p>Social Security and employer defined-benefit pensions are left out, because their future income can’t easily be turned into a current value (2025 SCF report, Appendix A).</p>
      <p>The unit is the <strong>family</strong> (close to a household), grouped by the age of the family’s reference person. The figures describe families, not individuals.</p>
      <p class="src">Source: Federal Reserve, 2025 SCF report, Appendix A.</p>
    </section>

    <section class="card prose" id="change">
      <h2>Change from 2022 to 2025</h2>
      {stat_p(f"Families under 35 had a median net worth of {k(FED['under35'][1])} in 2025, down 23% from 2022 in inflation-adjusted terms (Federal Reserve, 2025 SCF).")}
      {stat_p(f"Families 75 and older had a median net worth of {k(FED['75plus'][1])} in 2025, up 37% from 2022 (Federal Reserve, 2025 SCF).")}
      {table(["Age", "Median 2022", "Median 2025", "Change", "Mean 2022", "Mean 2025", "Change"], rows_d)}
      <p class="src">Thousands of 2025 dollars. {SRC_R} The Fed adjusts 2022 values to 2025 dollars with the current-methods CPI.</p>
    </section>

    <section class="card prose" id="methodology">
      <h2>Methodology</h2>
      <ul>
        <li><strong>Survey:</strong> Federal Reserve Board, 2025 Survey of Consumer Finances, conducted every three years. Report released Oct 9, 2026.</li>
        <li><strong>Sample:</strong> 4,367 families interviewed in 2025 (4,602 in 2022). The public Summary Extract has 4,360 families.</li>
        <li><strong>Weights:</strong> every figure uses the extract’s survey weights (WGT).</li>
        <li><strong>Missing answers:</strong> the Fed fills in missing answers with multiple imputation, so the extract holds five versions (implicates) of each family. RogueIQ pools all five, weighted, which is the same approach that reproduces the Fed’s public-data tables.</li>
        <li><strong>Unit:</strong> families, grouped by the age of the reference person.</li>
        <li><strong>Dollars:</strong> 2025 dollars. The Fed converts 2022 values with the current-methods CPI.</li>
        <li><strong>Exclusions:</strong> people on the Forbes 400 list are excluded from the sample.</li>
        <li><strong>Percentiles:</strong> a percentile is the first net worth value where the cumulative weight reaches that share, rounded to the nearest $10.</li>
        <li><strong>Limits:</strong> the survey is a snapshot of balance sheets at the time of the interview (mostly April–December 2025, with about one-seventh of interviews in January–May 2026). The tails are noisy.</li>
      </ul>
      <ul class="srcs">{links}</ul>
      <p><a href="/net-worth-by-age/networth-by-age-2025.csv">Download the data (CSV)</a> · <a href="/agents/#networth">Net worth by age API docs</a> · <a href="/net-worth-by-age/api/openapi.json">OpenAPI</a></p>
      <p class="src">Data note: the underlying data are public Federal Reserve data. If you reuse these figures, please credit the Board of Governors of the Federal Reserve System, 2025 Survey of Consumer Finances, and RogueIQ for the computed percentiles.</p>
    </section>

    <section class="card prose" id="faq">
      <h2>Frequently asked questions</h2>
      {faq}
    </section>

    <section class="card prose" id="cite">
      <h2>Cite this</h2>
      <p id="cite-text" class="cite">{e(cite)}</p>
      <button type="button" class="btn btn-outline" id="cite-copy">Copy citation</button>
      <p class="links-top"><a href="/wire/">Today’s official money releases on the RogueIQ Wire</a></p>
    </section>
    <script>
      (function () {{
        var t = document.getElementById("cite-text");
        t.textContent = t.textContent.replace("{{date}}", new Date().toLocaleDateString("en-US", {{ month: "short", day: "numeric", year: "numeric" }}));
        document.getElementById("cite-copy").addEventListener("click", function () {{
          var b = this; navigator.clipboard && navigator.clipboard.writeText(t.textContent).then(function () {{ b.textContent = "Copied"; }});
        }});
      }})();
    </script>'''

def put(s, tag, content):
    return re.sub(rf"(<!-- {tag} -->\n).*?(\s*<!-- /{tag} -->)", lambda mm: mm.group(1) + content + mm.group(2), s, flags=re.S)

idx = os.path.join(ROOT, "index.html")
s = open(idx).read()
s = put(s, "SEO:HEAD", head(TITLE, DESC, URL, graph(URL)))
s = put(s, "SEO:HERO", HERO)
s = put(s, "SEO:BODY", body())
open(idx, "w").write(s)

# ---------- CSV ----------
lines = ["age_group,stat,value_2025usd,source,computed_by"]
FS = "Federal Reserve 2025 SCF report Table 2"
XS = "Federal Reserve 2025 SCF Summary Extract"
for b in BR + [{"id": "all", "label": "All families"}]:
    i = b["id"]; lab = b["label"].replace("–", "-")
    lines += [f"{lab},median,{int(round(FED[i][1]*1000))},{FS},Federal Reserve", f"{lab},mean,{int(round(FED[i][3]*1000))},{FS},Federal Reserve"]
    if i != "all":
        lines += [f"{lab},p{q},{P(b,q)},{XS},RogueIQ" for q in (1, 5, 10, 25, 50, 75, 90, 95, 99)]
open(os.path.join(ROOT, "networth-by-age-2025.csv"), "w").write("\n".join(lines) + "\n")

# ---------- per-age pages ----------
TOP = s[:s.index("<body>")]
TOP = TOP[:TOP.index("  <!-- SEO:HEAD -->")]
REST = s[s.index("  <!-- /SEO:HEAD -->") + len("  <!-- /SEO:HEAD -->"):s.index("<body>")]
REST = REST.replace('href="raven-64.png"', 'href="../raven-64.png"').replace('href="style.css"', 'href="../style.css"')
NAV = s[s.index("  <header"):s.index("</header>") + 9].replace('src="raven-64.png"', 'src="../raven-64.png"')
FOOT = s[s.index('    <footer class="footer">'):s.index("    </footer>") + 13]
for b in BR:
    i = b["id"]; slug = SLUG[i]; url = f"{URL}{slug}/"; who = LONG[i]
    f = FED[i]
    name = "under 35" if i == "under35" else "75 and older" if i == "75plus" else b["label"]
    title = f"Net Worth {('Under 35' if i=='under35' else '75 and Older' if i=='75plus' else 'Ages ' + b['label'])}: 2025 Fed Data | RogueIQ"
    desc = f"Median net worth for U.S. families {who} was {k(f[1])} in 2025 (Fed SCF, released Oct 9, 2026), plus percentiles computed by RogueIQ."
    rows = [[f"{q}th" if q not in (1,) else "1st", d(P(b, q))] for q in (1, 5, 10, 25, 50, 75, 90, 95, 99)]
    others = " · ".join(f'<a href="/net-worth-by-age/{SLUG[x["id"]]}/">{"Under 35" if x["id"]=="under35" else "75+" if x["id"]=="75plus" else x["label"]}</a>' for x in BR if x["id"] != i)
    trend = "down" if f[4] < 0 else "up"
    page = f'''{TOP}{head(title, desc, url, graph(URL, faq=False, extra_crumb=(f"Net worth {name}", url)))}{REST}<body>
{NAV}
  <main class="container">
    <section class="hero">
      <p class="eyebrow"><a href="/net-worth-by-age/">Net worth by age</a> / {e(name)}</p>
      <h1>Net worth for families {e(who)} (Fed 2025 data)</h1>
      <p class="lede">Median net worth for U.S. families {e(who)} was {k(f[1])} in 2025, {trend} {abs(f[4])}% from {k(f[0])} in 2022 in inflation-adjusted terms, according to the Federal Reserve’s 2025 Survey of Consumer Finances (released Oct 9, 2026).</p>
      {UPD}
    </section>
    <section class="card prose">
      <h2>Median and mean, 2022 and 2025</h2>
      {table(["", "2022", "2025", "Change"], [["Median", k(f[0]), k(f[1]), pc(f[4])], ["Mean", k(f[2]), k(f[3]), pc(f[5])]])}
      <p class="src">{SRC_R}</p>
      <h2>Percentiles, 2025 (computed by RogueIQ)</h2>
      {table(["Percentile", "Net worth"], rows)}
      <p class="src">{SRC_X} Rounded to the nearest $10. Based on {N_EXTRACT[i]:,} families in the public extract.</p>
      <p>RogueIQ’s computed median for this group is {d(b["median"])}, against {k(f[1])} in the Fed’s report; the report uses the Fed’s internal data and the public extract is altered to protect privacy. The top percentiles rest on few families, and the SCF excludes the Forbes 400.</p>
      <p><a class="btn" href="/net-worth-by-age/">Check where you stand (runs in your browser)</a></p>
      <p class="links-top">Other age groups: {others}</p>
      <p class="links-top"><a href="/net-worth-by-age/#methodology">How we calculate percentiles</a> · <a href="/agents/#networth">Use this data from your AI agent (free MCP + API)</a></p>
    </section>
{FOOT}
  </main>
</body>
</html>
'''
    os.makedirs(os.path.join(ROOT, slug), exist_ok=True)
    open(os.path.join(ROOT, slug, "index.html"), "w").write(page)
print("ok", len(lines) - 1, "csv rows")
