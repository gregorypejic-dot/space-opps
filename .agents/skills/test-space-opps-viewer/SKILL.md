---
name: test-space-opps-viewer
description: Run local browser checks for the static digest viewer and publisher without modifying published digests.
---

# Local digest viewer testing

## Devin Secrets Needed
None for the static viewer or publisher. Do not run live source collection just to test the viewer.

## Setup
- From the repository root, copy `docs/` into a temporary directory and serve the copy with `python -m http.server 8766 --directory <scratch>/docs`.
- Check occupied ports first; another session may already use 8765.
- No build step or dependency installation is needed for the viewer or `python -m space_opps.publish`.

## Runtime checks
- Use real published digests for baseline counts and rendering. Spot-check agency links through the browser.
- For multiple runs, copy an existing Markdown file to `<scratch>/out/digest.md`, alter its date and Window counts, copy its CSV to `opportunities.csv`, and run the publisher from the repository root with `--out`, `--docs`, and `--date`.
- Clearly label synthetic content as test fixtures. Never publish it into tracked docs.
- Compare `a.href` or URLSearchParams with source URLs, especially URLs containing `&`; HTML serialization correctly contains `&amp;`, but the browser URL must not.
- Test both fresh page loads with a hash and same-document hash changes.
- Temporarily replace only scratch `digests/index.json` with `[]` or remove it for empty/error states, then restore it.
- At 400px width inspect both pixels and document scroll width; long unbreakable titles can force grid overflow.
- Check both header and footer Cognition lockups and browser console. A favicon 404 when opening raw Markdown is distinct from a viewer resource failure.
