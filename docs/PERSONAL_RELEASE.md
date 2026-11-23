### Additional verified browsing sources (JS-018)

The Benin local-source directory also links to **WabaJob** and **Opportafrik's Cotonou page**, which displayed Benin-area advertisements during a public-web check on November 23, 2026. These are **links for human browsing and assisted copy/review/import only**. Neither is configured as an automated jobs API; live results, freshness, suitability, permission to reuse, and vacancy counts are not guaranteed. Use the original listing's application instructions and confirm deadline and employer independently. No backend fetch or scraping was added.

## Evidence checkpoint — November 23, 2026 UTC

A read-only GitHub-hosted probe succeeded at 16:43:47 UTC in
workflow run 45219737203. **Dev Global Jobs returned a valid response
containing zero records for `country=bj` in that sampled request**.
Remotive returned 15 records in its public response; 6 had geographic
strings potentially compatible with Benin, before role-keyword,
employment-eligibility, freshness and individual-application checks.
These are observations at one instant, **not** a prediction of future feed
availability or proof that no on-site jobs exist. The result confirms an
important release caveat: keyless automated discovery cannot currently
be relied on for actual Benin workplace vacancies.

ANPE Bénin's official **SALEC** portal is available as another direct
directory link; it is not an API or automatically ingested data source.
ReliefWeb's humanitarian jobs API is a promising later source, but its
current documentation requires a pre-approved `appname` and applicable
reuse terms. It is not included in automated job ingestion without
registration and permission.

## Live provider coverage and readiness audit (JS-016)

The pull-request CI workflow now includes a **read-only, informational live
source probe**. It makes at most one bounded API request to each of
Dev Global Jobs (country `bj`, first 100 records) and Remotive (public
remote feed). The diagnostic reports the observation time, basic response
shape, the number of structurally usable Benin-local records in the sampled
Dev Global Jobs page, and the number of Remotive records whose declared
geographic restrictions may include Benin. It does **not** print job titles,
employer names, descriptions, URLs, private profiles or application data, and
it does not persist vacancies.

If a provider is inaccessible, malformed or its response schema changes,
its coverage is **unknown**, not zero. A live response sample is **not**
proof that the application can import those jobs end-to-end, that the full
market is covered or that the jobs are current. The probe is informational,
not an application CI gate: provider outages must not block development.
It runs on pull requests and can also be triggered manually through GitHub Actions workflow_dispatch. There is no schedule; avoid repeated manual requests to respect provider limits. The Remotive
public API asks developers to limit use and preserve attribution.

To review results, open the PR's GitHub Actions CI run or launch an opt-in manual CI workflow from Actions (select the intended branch), then check
**Live source coverage audit (informational)**. If it reports incompatible
schema, update the provider adapter only after reviewing the actual public
API's documented fields; do not fabricate missing fields or quietly mark an
unreachable provider as empty. Final acceptance still needs a browser and
real candidate-controlled workflow testing.

Sources: https://devglobaljobs.com/developers and
https://remotive.com/remote-jobs/api

---

## Unified automatic Benin vacancy discovery (JS-015)

**Discover → Country = BJ → Any work arrangement** now combines jobs
physically advertised as Benin-located by Dev Global Jobs with **Remotive**
remote jobs whose published geographic restrictions include Benin. If a valid,
approved Optioncarriere/Careerjet publisher configuration is present, its
Benin workplace results are also searched independently, even when the other
sources return jobs. Entries are interleaved, conservatively deduplicated by
employer, title and city, then limited to the requested result count. Remote
positions retain their remote source and geographic restriction; they are
**not** represented as physically located in Benin.

**Remote only** still searches the no-key Remotive feed and preserves the
original geography and eligibility restrictions. Other countries keep their
previous provider routing. Results can be filtered on the page by source,
Benin workplace versus eligible remote, and existing advisory relevance/match
signals without triggering another provider call. A breakdown reports only
the records **returned in the current response**, not the number available at
each provider or complete national vacancy coverage. CV data is not sent
to providers. The app still requires profile and job evidence review before
making an application decision.

**Known limitations:** Without approved Careerjet publisher credentials, the
system never queries Careerjet. ANPE and other Benin job sites have no
authorized automatic feed and remain navigation/assisted import sources.
Provider searches can fail and the existing API reports such failures rather
than fabricating successful empty results. The merge caps total results, so
use narrower search terms for more targeted discovery; live provider coverage
is not verified by mocked regression tests.

---

# Career Intelligence — local-first personal release

**Audience:** individuals who clone the public source and run a personal copy on a trusted computer. This is a **MIT-licensed original-code prototype for personal use**, not a hosted SaaS platform, a multi-user server, or a verified job-search service.

## Fastest supported start

1. Install Docker Desktop / Docker Engine with Compose and obtain the source:

   ```sh
   git clone https://github.com/Tadeni00/career-intelligence.git
   cd career-intelligence
   docker compose up --build -d
   docker compose ps
   ```

2. Open **http://127.0.0.1:4173** on the *same machine*. Use a trusted browser profile. API reference: http://127.0.0.1:8011/docs.
3. Upload and review CV evidence; confirm a CV profile. Edit preferred roles, target locations and remote preferences in **Career Profile**, then explicitly **Save changes**.
4. Open **Discover Jobs**, select your CV profile, choose **Use profile preferences** or a saved search, check country/remote settings, and press **Search**. JSearch/Indeed requests require configured provider credentials and may consume quota; Benin remote-only Remotive search needs no key. The Docker API defaults to offline AI, which is not the same as validated matching.
5. Review the role, location restrictions, work authorization, salary units and posting date before applying. **Open the employer site**, submit there, and **manually confirm submission** under **Applications**. Opening the link does *not* send an application.
6. To shut down without deleting database/storage: `docker compose down`. **Avoid** `docker compose down -v` unless deliberately destroying both named volumes.

### Benin Republic and countries outside the provider's default coverage

Select `bj` in the two-letter country-code field (or enter another ISO 3166-1 alpha-2 code). Set **Remote only** to use the keyless Remotive public feed for Benin. The feed is global rather than locally focused: it only includes vacancies whose declared remote-work region clearly includes Benin (e.g. Worldwide, Africa, West Africa, Benin). Ambiguous restrictions, unverified work authorization and potentially stale postings are not certified matches. Remotive requires attribution and links back to each original listing; displayed Remotive jobs may be delayed by 24 hours. The local API caches the feed for six hours to respect rate limits. [Official Remotive API terms](https://remotive.com/remote-jobs/api).

For **on-site or hybrid jobs in Benin**, Search now requests **Dev Global Jobs** using its documented country/keyword API, without an API key. Only records with an explicit Benin country, an identifiable local location, and a vendor-hosted original listing URL enter the matching and shortlisting pipeline. Provider data may be sparse, partial, stale or incorrectly labeled; the result count is **not proof of comprehensive Benin coverage**. Salary and employment type remain unverified when missing. The provider permits non-commercial personal/research use within its published limits, requires visible **Powered by Dev Global Jobs** attribution and links to its own job pages, and requires written permission for commercial redistribution. See [provider API and terms](https://devglobaljobs.com/developers).

### Safe direct URL preview for published Greenhouse and Lever jobs

The import form can now **preview a direct public Greenhouse or Lever job URL**
by calling those providers' documented read-only job APIs (Greenhouse Job Board
API and Lever Postings API). This is an explicit action: enter the original
direct job URL, select **Preview supported URL**, review the returned draft,
fill any missing information (Lever may not return the employer name), and
press **Save vacancy and review**. Previews are never auto-saved, do not
run CV matching and never submit applications.

Security restrictions: strict allowlisting of the original job-page hosts and
paths, fixed official API destination hosts, HTTPS only, no redirects, no
arbitrary hostname fetching, and no credentials. The returned content is plain
text only. Expired and missing jobs must fail visibly. The current supported
direct URL hosts are `boards.greenhouse.io`,
`job-boards.greenhouse.io`, `jobs.lever.co` and `jobs.eu.lever.co`.
Other sources, including ANPE Bénin and local Benin job boards, retain the
**paste JobPosting HTML / description + review** path until a permitted
machine-readable feed is confirmed.

References:
- Greenhouse public Job Board API: https://docs.greenhouse.io/job-board
- Lever public Postings API: https://github.com/lever/postings-api

### Assisted extraction without accessing third-party websites

Jobs → Import a vacancy also accepts pasted **JobPosting JSON-LD** or
copied page HTML with an embedded `application/ld+json` block. The browser
parses exactly one structured job record, prefills title, employer, locality,
description and explicitly stated remote status, then requires the user to
review and save the fields using the same existing import endpoint. Missing
work arrangement is reported as unknown, not assumed on-site. HTML is handled
as untrusted text and scripts are not executed; the extracted draft is not
automatically saved. Unsupported or ambiguous HTML falls back to manual entry.
**No remote URL fetching, ANPE scraping, bypassing access controls or
automated third-party redistribution is introduced.** A source's presence of
JSON-LD does not itself grant permission to crawl it.

### Import an on-site or hybrid job without a provider API key

The **Jobs → Import a vacancy** form works for any country, including Benin.
Use Discover's Benin local source directory (ANPE Bénin, government recruitment
notices, EmploiBenin, etc.) to locate a vacancy. Copy its original description
and link into the import form. Confirm the job title, employer, workplace and
work arrangement only if explicitly stated, then save. The new record is
marked `manual_import` and appears in **Jobs**. Open its detail page to
extract requirements, run an advisory CV match and use the existing application
workflow. The original link is preserved; repeating an identical link returns
the existing job without overwriting it.

**Limits and safety:** importing a bare URL does not automatically download or
parse that webpage. The user must paste at least 30 characters of description
and confirm the key fields. This intentionally avoids server-side arbitrary
web requests (SSRF), unauthorised scraping, browser/CAPTCHA bypass, and
unverified claims of a vacancy's currency or authenticity. No CV details are
sent to the vacancy website. The importer accepts HTTPS original links and
does not treat a saved posting as proof it is still accepting applications.
A future permissioned fetcher can be added per-source without changing the
manual workflow. The source directories are not ingested automatically.

### Optional second Benin source — Optioncarriere/Careerjet publisher API

Career Intelligence supports the official **Optioncarriere/Careerjet** publisher search API for `fr_BJ` as an **additional independent search even when Dev Global Jobs returns vacancies**. An approved publisher account and registration for the referral page are required; this is not the high-volume paid Careerjet Job Data API. Without configuration, no Careerjet API call is made.

Set these four fields in a **local untracked** `.env` (see `.env.example`):

- `CAREERJET_PUBLISHER_KEY`: your approved Careerjet publisher API key.
- `CAREERJET_USER_IP`: your **actual public** IPv4/IPv6 address for the person conducting the search, not the Docker container, router LAN address or a placeholder.
- `CAREERJET_USER_AGENT`: the actual browser user-agent for that same person, not a fabricated bot header.
- `CAREERJET_REFERER`: the **registered HTTPS publisher search page** on which the request originated. A localhost URL or an unregistered page is not a valid substitute.

The configured publisher is queried for each Benin-local search, subject to publisher quotas, **including when the free feed returns jobs**. The combined results are capped at the requested count after suppressing clear cross-provider duplicates (same employer, job title and city); distinct opportunities remain source-attributed. This can improve breadth but does not prove completeness. If either configured source fails, the search reports a provider failure rather than implying complete results.

The integration is therefore designed for the app's single-person trusted-local deployment, not a shared public backend. It deliberately does not guess IP addresses, spoof user-agent strings or substitute an invented public referral page. If you do not have a legitimate registered publisher site and requester metadata, **leave this provider disabled**. Provider quota and publisher terms remain applicable; approval to use the key cannot be assumed. Only the provider key is transmitted as Basic authentication to the published Careerjet API host. Requester IP, browser agent and referrer are sent to the provider because its official API contract requires them; CV content is not sent. The API may return ambiguous locations, fewer results or errors, which are not treated as verified local vacancies. The provider returns referral links, and actual work arrangements, salaries and employer eligibility require manual validation.

Publisher documentation: https://www.optioncarriere.bj/partners/api/python

**CAPPR/Trouve Ton Emploi** maintains a more Benin-focused database but its structured API requires a paid subscription or special licence. Its public listing directory remains a navigation link, not an unauthorized scraping source: https://skills.capprafrica.org/fr/tarifs

After combining and conservatively deduplicating the two API result sets, Discover also offers BeninFindJob, EmploiBenin, Trouve Ton Emploi and Emplois Bénin as original-source entry points. Those links are **not scraped or automatically imported**. Verified vacancies can still be added manually. Broader local API ingestion (such as licensed CAPPR or Careerjet publisher integrations) requires the corresponding permission or registered key.

### Live vacancy provider setup

The Compose file accepts `JSEARCH_API_KEY` from the invoking shell or a local untracked `.env` file. Obtain a valid key for the configured RapidAPI provider if you want live search. Do not add it to the repository or share it. Example for Bash-compatible shells:

```sh
export JSEARCH_API_KEY="your-own-key"
docker compose up --build -d
```

A provider key may be subject to separate pricing and terms. Provider availability and country coverage are not guaranteed; Indeed fallback may be rate-limited. Do not assume that an empty result means no suitable jobs exist.

### No key? Still useful

You can review and prepare a CV, enter vacancies manually, run the offline matching/analysis features with their known limitations, open stored employer links and track applications. Live search will not operate without a valid provider credential.

## Release acceptance checklist

- [x] Docker Compose default ports bound to loopback only
- [x] Production-mode API refuses to start without a supported security model
- [x] Browser supports CV profile selection, job discovery, sorting, safe external application links, shortlisting and application tracking
- [x] User explicitly confirms external application submission
- [x] Saved discovery search preferences and explicit profile editing
- [x] Unknown work arrangement does not appear as on-site; salary lacks invented currency, period or thousand-unit suffix
- [x] Automated frontend, backend, frozen-artifact and local deployment quality checks in GitHub Actions
- [ ] Manual end-to-end walkthrough on a fresh machine with a non-sensitive test CV and one live provider search; **not evidenced by CI**
- [x] Remove five personal CV/profile exports from the current branch and forbid tracking those paths again.
- [ ] Historical exposure remains: **[SEC-003](https://github.com/Tadeni00/career-intelligence/issues/3) stays OPEN**. History rewriting requires owner approval, and public copies/caches may persist.
- [ ] Verify actual live-provider coverage, current vacancies, application URLs, and candidate suitability with an independently reviewed sample before making accuracy claims

The original project code is [MIT licensed](../LICENSE). Installed third-party components retain their own terms; **PyMuPDF is AGPLv3/commercial**, so review [third-party licensing notes](THIRD_PARTY_LICENSES.md) before redistributing an integrated application.

## Non-goals for this personal-use release

No user registration, password login, billing, public hosting, applicant automation, unsupervised job applications, or shared online database. Each individual controls a **local installation**. A public GitHub repository means code can be viewed and cloned; it does **not** mean its API should be exposed to the public internet.

The matching recommendation is advisory and research-limited. Work authorization, cross-border remote eligibility, employer sponsorship and vacancy opening must be checked by the person applying. Never transmit real CV content or tokens in bug reports. Do not commit `.env`, downloaded CVs, extracted personal contact details or private records. If the repository will be used by others, resolving **SEC-003** is especially important.

## Release decision

**Usable for trusted-local personal testing with the above limitations. Not cleared for public hosting, verified eligibility screening, or unattended applications.** No change to the V3.4 research governance gates is implied by a personal release.
