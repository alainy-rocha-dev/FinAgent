# Docs screenshots

Captures screenshots of the Reversa documentation site (`_reversa_docs/`) with Playwright.

```bash
cd tools/docs-screenshots && npm install && cd -
python -m http.server 8085 --directory _reversa_docs &   # serve the site
node tools/docs-screenshots/capture_screenshots.js        # run from the repo root
```
