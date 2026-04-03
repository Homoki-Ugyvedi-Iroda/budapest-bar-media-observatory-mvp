# TODO

## Pending tasks

- [ ] **a) Check Hungarian translations** — review all Hungarian UI labels and flash messages for accuracy and consistency
- [ ] **d) Optimize for specific bar content** — tune keyword filtering and selectors for Austrian and Polish bar associations specifically
- [ ] **CSS selectors** in `sites.yaml` for individual sites — currently most sites use generic fallback (all links), producing noise; selectors must be set manually using browser dev tools (F12)
- [ ] **JavaScript-rendered pages** — sites that load content dynamically (e.g. OZS, UNBR) require Playwright or similar; these are flagged in logs for manual follow-up
- [ ] **Scheduled parser runs** — must be configured manually in PythonAnywhere
- [ ] Add more sites to `sites.yaml` (e.g. further Polish regional bars, Baltic bars)
- [ ] Refine keyword filtering based on false positives/negatives from initial runs
- [ ] Automate PDF text extraction (e.g. with `pdfplumber`)
- [ ] Integrate email sending into the drafter
- [ ] Build an archive view for browsing past newsletters
