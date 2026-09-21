# space_opps

Scrapes public federal portals for space-related business opportunities (US Space Force, NASA, NRO,
SDA, GSA Assisted Acquisition Services) and writes a weekly digest.

## Sources

| Source | Method | Notes |
|---|---|---|
| SAM.gov | Opportunities API v2 | Needs `SAM_API_KEY`. Agency queries (USSF, SSC, NASA, NRO, SDA, GSA FAS/AAS) + space title keywords. GSA FAS results are kept only if space keywords match. Non-federal keys have a small daily request quota (resets 00:00 UTC); a full run uses ~13 requests, so avoid re-running the SAM source more than once a day. |
| Grants.gov | search2 API | NASA grants + space/satellite keyword hits across agencies. |
| NSPIRES | JSON | NASA research solicitations (ROSES etc.) via the DataTables feed behind the open-solicitations page; the host only offers RSA-key-exchange ciphers, so it gets a relaxed TLS adapter. Keeps items released in the window or due within 30 days. |
| NASA SBIR/STTR | HTML | sbir.nasa.gov solicitations + nasa.gov/sbir_sttr opportunities. |
| SSC Front Door | HTML | Space Systems Command industry portal (ssc.spaceforce.mil, bot-blocked) plus the Front Door events page (sscfrontdoor.experience.crmforce.mil); the latter is a Salesforce Experience site rendered client-side, so plain HTTP yields 0 results and the digest reports the gap. |
| SpaceWERX | HTML | Challenges / open topics. |
| SDA | HTML | Space Development Agency opportunities page. |
| DIU | HTML | Open solicitations, filtered to space keywords. |
| DoD SBIR/STTR | HTML | Topics app is JS-heavy; best-effort. |
| NSTXL/SpEC | HTML | Space Enterprise Consortium page (info.nstxl.org/spec); generic CTA links ("Register Here") are titled from the nearest heading. Full RFPs are member-only. |
| GSA AAS | HTML + SAM | gsa.gov/assisted-acquisition-services/industry only links to Interact and a Tableau dashboard; AAS/FEDSIM solicitations themselves are on SAM.gov (covered by the FAS query) or eBuy (login-only, not scraped). |
| DTIC DoD agencies (DAFA) | HTML | defenseinnovationmarketplace.dtic.mil/business-opportunities/dod-agencies: one accordion per Defense Agency/Field Activity (DARPA, MDA, DTRA, NGA, NSA…); solicitation/BAA links are titled `<Agency>: <link>`. Dead fbo.gov links are dropped. Its "Contract Opportunities" table is historical (last posting 2019); rows are kept only while their response date is in the future and link to a SAM.gov keyword search on the solicitation number. |
| Commerce: Office of Space Commerce | HTML + RSS + SAM | space.commerce.gov: the DOC-agencies opportunities page, TraCSS page (registration, specs, forums), Future NOAA Satellite Architecture and Commercial Data Program industry-day pages (article body only), plus the site RSS feed for new posts (calls for interest, RFIs, forums). SAM notices from the Office of Space Commerce are always kept (`DOC-OSC`). |
| Commerce: NOAA (NESDIS, CRSRA, TPO) | HTML + SAM | techpartnerships.noaa.gov home and SBIR funding page (reports the page's own NOFO status when no solicitation is linked). SAM `NATIONAL OCEANIC AND ATMOSPHERIC ADMINISTRATION` query; NOAA notices are kept only on an outer-space keyword hit (satellite, remote sensing, launch…), so fisheries/ship/weather-service buys are dropped. |

Not covered (login required): NRO ARC (acq.westfields.net), GSA eBuy, NSTXL member portal.

"Space" means outer space. Keywords (`SPACE_KEYWORDS` in `config.py`) match at a word start, so
`spacer`, `cyberspace`, `greenspace` never hit. When `space` is the only keyword hit, the item is
dropped if it reads as real estate (`REAL_ESTATE_SPACE`: lease/RLP, office/hangar/warehouse space,
square footage, confined space…). Everything from USSF, NASA, NRO and SDA on SAM.gov is kept
regardless of keywords, since enabling functions at those agencies are in scope.

## Run

```bash
pip install -r requirements.txt
export SAM_API_KEY=...        # https://sam.gov -> Account Details -> API Key
python -m space_opps.main --since-days 7 --out out/
```

Outputs `out/opportunities.json`, `out/opportunities.csv`, `out/digest.md`. Items not present in
`state/seen.json` are flagged **NEW**; the state file is updated after each run (skip with
`--no-update-state`). Limit sources with `--sources sam.gov,grants.gov,nspires`.

Every item carries a one-sentence `summary` (shown under each bullet in the digest and as a CSV/JSON
column) built by `space_opps/summarize.py` from data already fetched: for SAM.gov the notice type,
PSC/NAICS title (offline tables in `space_opps/data/`), issuing office, set-aside and place; for
NSPIRES the announcement type and number; for HTML sources the first descriptive sentence on the
page, else a per-source template. No extra API calls are made.

Software-related opportunities (greenfield development, brownfield modernization/sustainment,
software licenses/SaaS) are flagged by `space_opps/software.py` from software NAICS codes
(541511/541512/541519, 511210/513210, 518210), software PSC codes (7030, D302/D306/D307/D308/D318/D319/D399,
DA*, DB10, DF*, DG*) and word-start keyword matches. They get a **SOFTWARE** marker, a `Software:` reason
line and their own section at the top of the digest, an `is_software` CSV/JSON column plus the
`software` reasons list, and a badge/"Software only" filter on the site.

HTML sources are brittle by nature; a run logs a warning whenever a page yields zero links so a
site redesign is noticed rather than silently dropping results.

## Website (GitHub Pages)

`docs/` is a static viewer for the digest history, served at
https://gregorypejic-dot.github.io/space-opps/ once Pages is enabled
(repo Settings > Pages > Deploy from a branch > `main` / `/docs`). After each run:

```bash
python -m space_opps.publish --out out/ --docs docs/   # copies out/ to docs/digests/<date>.{md,csv}, rebuilds index.json
```

`docs/index.html` reads `docs/digests/index.json`; nothing else needs editing. Dated files in a
legacy top-level `digests/` directory are imported automatically.

## Tests

```bash
python -m pytest -q
```
