# Local deployment security boundary (CI-001)

## Current supported boundary

Career Intelligence is **single-user software, not a public multi-tenant service**. The FastAPI dependency `current_candidate()` selects a shared candidate without authenticating the caller, and several document endpoints load objects by numeric ID. The Compose stack must therefore be accessed only by trusted local users. Its database password is a development default and must not be used for a remotely exposed database.

`docker-compose.yml` publishes the console (4173), API (8011), and PostgreSQL (5433) on `127.0.0.1` only. Internal container-to-container networking continues to work, and existing volumes are retained. Open the console at `http://127.0.0.1:4173/`. For access from another machine use an appropriately secured SSH local port-forward to a trusted host; **do not bind the Docker ports to `0.0.0.0`** as a convenience.

Loopback binding reduces accidental LAN/Internet exposure; it does **not** provide authentication, protect against untrusted local users/processes, or make the application safe to publish via a public reverse proxy. Container-level firewalling or cloud security-group rules are not substitutes for proper application authorization.

## Production-mode startup guard

The API rejects startup when `ENVIRONMENT=production` while session authentication and per-record authorization are absent. This is an intentional fail-closed guard, not a claim that `ENVIRONMENT=development` is safe to expose remotely. The Compose stack remains trusted-local only. No configuration flag should be added to bypass this guard without implementing and testing a genuine authorization boundary.

## Public repository data review

The repository contains files that appear to include CV/profile information, including `cv/`, `cv_text.txt`, `val_extraction.json`, `val_profile.json`, and `val_profile_fixed.json`. Before sharing or cloning widely, review whether they include personal contact details or other data that should not be public. If they must be removed, scrub both the current branch **and Git history**, consider copies/forks/caches irrecoverable, and rotate any credentials discovered. Do not assume that adding a `.gitignore` entry or deleting the working-tree file removes data from previous commits.

The `.gitignore` file excludes new local files in `cv/` and selected root-level profile export paths from routine Git staging. **Previously tracked files and their historical Git copies are not affected** by ignore rules; [SEC-003](https://github.com/Tadeni00/career-intelligence/issues/3) remains open. Ignore rules are not a defense against an explicit `git add -f` or against past public clones.

## Requirements before hosting publicly

- Implement a real user session/authentication mechanism and test access denial for unauthenticated requests.
- Restrict every candidate, CV, generated document, job, match, and application lookup to the authenticated owner (including legacy record-ID endpoints).
- Use separate production credentials, secret management, and `DEBUG=false`; remove development database defaults and fail closed on missing mandatory production secrets.
- Add rate limiting, safe error handling, document retention/deletion, backups, audit logs, and a threat-model review.
- Test end-to-end authorization, including cross-user IDOR cases, before any public exposure.

**Scope:** CI-001 reduced default network exposure. SEC-006 adds a production-startup guard and ignore rules for future local exports. Neither implements authentication, removes existing public history, or changes matching/benchmark code. The V3.4 governance gates remain unchanged.
