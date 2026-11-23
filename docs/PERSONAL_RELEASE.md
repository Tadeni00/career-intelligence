# Career Intelligence — local-first personal release

**Audience:** individuals who clone the public source and run a personal copy on a trusted computer. This is a **source-available prototype for personal use**, not a hosted SaaS platform, a multi-user server, or a verified job-search service.

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
4. Open **Discover Jobs**, select your CV profile, choose **Use profile preferences** or a saved search, check country/remote settings, and press **Search**. Search requests require provider credentials and may consume paid quota. The Docker API defaults to offline AI, which is not the same as validated matching.
5. Review the role, location restrictions, work authorization, salary units and posting date before applying. **Open the employer site**, submit there, and **manually confirm submission** under **Applications**. Opening the link does *not* send an application.
6. To shut down without deleting database/storage: `docker compose down`. **Avoid** `docker compose down -v` unless deliberately destroying both named volumes.

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
- [ ] Review and remediate historically tracked personal CV/profile data in the public repository and Git history; **[SEC-003](https://github.com/Tadeni00/career-intelligence/issues/3) remains OPEN**. History rewriting requires owner approval, and public copies/caches may persist.
- [ ] Verify actual live-provider coverage, current vacancies, application URLs, and candidate suitability with an independently reviewed sample before making accuracy claims

## Non-goals for this personal-use release

No user registration, password login, billing, public hosting, applicant automation, unsupervised job applications, or shared online database. Each individual controls a **local installation**. A public GitHub repository means code can be viewed and cloned; it does **not** mean its API should be exposed to the public internet.

The matching recommendation is advisory and research-limited. Work authorization, cross-border remote eligibility, employer sponsorship and vacancy opening must be checked by the person applying. Never transmit real CV content or tokens in bug reports. Do not commit `.env`, downloaded CVs, extracted personal contact details or private records. If the repository will be used by others, resolving **SEC-003** is especially important.

## Release decision

**Usable for trusted-local personal testing with the above limitations. Not cleared for public hosting, verified eligibility screening, or unattended applications.** No change to the V3.4 research governance gates is implied by a personal release.
