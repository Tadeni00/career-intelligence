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

For **on-site or hybrid jobs in Benin**, the existing Indeed fallback remains but may be rate limited, may require a RapidAPI key, and is **not guaranteed to return local vacancies**. When selecting Benin (`bj`) with **Any work arrangement**, Discover now also presents verified navigation links to BeninFindJob, EmploiBenin, Trouve Ton Emploi and Emplois Bénin. These are **external source directories**, not scraped results or automatic imports. Visit original listings, verify details and use **Jobs** to add or track a vacancy manually. The links do not certify availability or employment type. Automated ingestion from these sites requires an appropriate API/feed or permission; no scraping was introduced. The application also supports adding verified jobs manually. Country code entry now accepts countries beyond the quick-selection list, but data-source coverage still varies; no country coverage is fabricated.

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
