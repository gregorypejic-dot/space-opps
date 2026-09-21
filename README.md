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

Not covered (login required): NRO ARC (acq.westfields.net), GSA eBuy, NSTXL member portal.

## Run

```bash
pip install -r requirements.txt
export SAM_API_KEY=...        # https://sam.gov -> Account Details -> API Key
python -m space_opps.main --since-days 7 --out out/
```

Outputs `out/opportunities.json`, `out/opportunities.csv`, `out/digest.md`. Items not present in
`state/seen.json` are flagged **NEW**; the state file is updated after each run (skip with
`--no-update-state`). Limit sources with `--sources sam.gov,grants.gov,nspires`.

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
