# Personal-use acceptance — one local walkthrough

Use a **fresh local clone** and a **synthetic CV**. The repository is public, but the running app remains loopback-only. Do not upload actual personal details for screenshots or bug reports.

## Prerequisites

- Docker Desktop or Docker Engine with Compose
- A disposable sample CV you are permitted to use
- Optional: your own valid JSearch/RapidAPI key to test live job discovery, with awareness of provider limits
- No real applicant contact details, credentials, or exported documents in Git commits

## Smoke-test checklist

1. [ ] Clone the public repo and run `docker compose up --build -d`. Confirm every published host binding shows `127.0.0.1` using `docker compose ps`. If containers fail, inspect `docker compose logs --tail=100`.
2. [ ] Open `http://127.0.0.1:4173` on the same computer. Verify the console loads and shows no unexpected API error.
3. [ ] Upload a synthetic PDF/DOCX CV, inspect extracted fields, correct mistakes and **confirm** the profile. Note if extraction omits fields or differs on retry.
4. [ ] Edit preferred job roles and locations in the Career Profile. Confirm input does not save on every keystroke; use **Save changes**, reload and verify fields persisted. Check **Discard changes** restores the last saved state.
5. [ ] Go to Discover Jobs, select the confirmed profile, use profile preferences to fill search fields and confirm that this action **does not start a provider request**. Save and reload a search preset. Confirm the country and location.
6. [ ] With a valid provider key, press **Search** for one realistic role and country; record the actual result count, provider errors or rate limits without leaking tokens. If no key is available, record this step as *not tested*, not passed.
7. [ ] Review at least three real returned postings, where available: confirm role/country, recency, duplicate warnings, requirements, remote-country restrictions and employer application URL. Note any listing that is expired, incorrectly located, inaccessible or unrelated.
8. [ ] Check that unknown remote status is **not** displayed as on-site, and salary values are **not** labelled with an unsupported currency or multiplied by 1,000. Treat missing pay currency/period as unknown.
9. [ ] Shortlist one suitable test posting. Inspect the job details and application readiness questions. Try preparing tailored CV and cover letter; check factual claims against the confirmed profile.
10. [ ] Open the stored employer apply link in a new tab. **Do not submit a real application as a test.** Confirm opening the link does not automatically mark the application as submitted.
11. [ ] Verify tracked applications, filtering and status display. Only use **I submitted this application** after an actual external submission; do not fake a submission merely to tick the test.
12. [ ] Stop the stack with `docker compose down`, without `-v`. Restart and check that previously saved profile/application data remains present.


## Benin discovery and vacancy-import acceptance (JS-017)

This section is **not yet executed**. It supplements the smoke test above; a green CI run is not a substitute for browser acceptance.

### Optional remote source audit — no local setup

From GitHub **Actions → CI quality gates → Run workflow**, select the current development branch, then inspect **Live source coverage audit (informational)**. This opt-in workflow makes only bounded read-only requests to the two public sources. Do not rerun it repeatedly: Remotive requests should be infrequent, and the workflow deliberately has no schedule. Report UTC observation time, provider status and counts only; do not copy vacancy descriptions, applicant details or secrets into CI discussions. A provider error yields **UNKNOWN**, never zero. A count from one sampled page does not establish nationwide coverage or end-to-end import success.

### Local/browser acceptance when ready

1. [ ] Select a confirmed synthetic profile, set **Country = BJ** and **Any work arrangement**, and click Search. Record source-specific result counts and errors independently; do not label remote jobs as physically located in Benin.
2. [ ] Select **Remote only** with BJ. Check that regional eligibility is explicit, not assumed from the word 'remote', and that original source/apply links remain accessible. A listed region is not verification of work authorization.
3. [ ] Test a directly hosted, public **Greenhouse** vacancy URL and a **Lever** vacancy URL using **Preview supported URL**. Confirm that preview makes no automatic save, matching or application submission; review missing company, salary, workplace and eligibility fields before saving.
4. [ ] Paste a JobPosting JSON-LD excerpt or copied HTML from an accessible job page. Confirm the extracted fields remain an editable draft; for an unsupported site, verify manual description plus URL entry is possible without arbitrary server-side fetching.
5. [ ] Use a genuine Benin local-source listing from the directory (where available) to test manual import and source attribution. Do **not** infer a site permits scraping, and do not manufacture a listing when none is available.
6. [ ] Verify source filters, local-versus-remote labels, conservative duplicate behavior and that provider outages display an error rather than a successful empty result.
7. [ ] Open an original employer application URL from an imported vacancy, verify safe external navigation and that the application remains unsubmitted until explicitly confirmed by the user.

**Release decision rule:** automated discovery may be marked functioning only for a source with confirmed end-to-end sample evidence; no claim of broad Benin on-site coverage is permitted from the current zero-record Dev Global Jobs observation. Manual Benin vacancy import can be accepted independently of automated discovery. Keep live-provider audit, browser acceptance and third-party terms as separate evidence categories.

## Report

Copy this concise summary into the release discussion (omit CV content and names):

- Local environment: OS / Docker version / browser
- Start-up and persistence: PASS / FAIL
- CV upload + profile save: PASS / FAIL
- Saved search with no provider call: PASS / FAIL
- Live search: PASS / FAIL / NOT TESTED; country, role, returned count and provider errors
- Review of real vacancies: number reviewed, valid apply links, stale/mismatched instances
- Shortlist, CV, cover letter and external apply link: PASS / FAIL / PARTIAL
- Tracking and non-automatic submission: PASS / FAIL
- Any reproducible defects with steps (no keys or CV personal data)

## Release stop conditions

- Any untrusted public network access to the running API or database
- Newly staged private CV/profile exports in the Git working tree
- Unsafe application URLs, lost records after ordinary restart, or application status set to APPLIED without user confirmation
- False claims of confirmed eligibility, salary currency, or live vacancies
- Regressions in mandatory GitHub Actions tests

**Status:** this is an unexecuted human checklist. Automated CI cannot substitute for it.

**Public distribution status:** original project code has MIT terms, with separate third-party obligations, including PyMuPDF AGPLv3/commercial. Five CV/profile exports have been removed from the current branch, but SEC-003 historical Git exposure remains open. Removing active files does not remove public Git history or external copies.
