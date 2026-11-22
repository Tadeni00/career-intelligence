# Local deployment security boundary (CI-001)

## Current supported boundary

Career Intelligence is **single-user software, not a public multi-tenant service**. The FastAPI dependency `current_candidate()` selects a shared candidate without authenticating the caller, and several document endpoints load objects by numeric ID. The Compose stack must therefore be accessed only by trusted local users. Its database password is a development default and must not be used for a remotely exposed database.

`docker-compose.yml` publishes the console (4173), API (8011), and PostgreSQL (5433) on `127.0.0.1` only. Internal container-to-container networking continues to work, and existing volumes are retained. Open the console at `http://127.0.0.1:4173/`. For access from another machine use an appropriately secured SSH local port-forward to a trusted host; **do not bind the Docker ports to `0.0.0.0`** as a convenience.

Loopback binding reduces accidental LAN/Internet exposure; it does **not** provide authentication, protect against untrusted local users/processes, or make the application safe to publish via a public reverse proxy. Container-level firewalling or cloud security-group rules are not substitutes for proper application authorization.

## Public repository data review

The repository contains files that appear to include CV/profile information, including `cv/`, `cv_text.txt`, `val_extraction.json`, `val_profile.json`, and `val_profile_fixed.json`. Before sharing or cloning widely, review whether they include personal contact details or other data that should not be public. If they must be removed, scrub both the current branch **and Git history**, consider copies/forks/caches irrecoverable, and rotate any credentials discovered. Do not assume that adding a `.gitignore` entry or deleting the working-tree file removes data from previous commits.

## Requirements before hosting publicly

- Implement a real user session/authentication mechanism and test access denial for unauthenticated requests.
- Restrict every candidate, CV, generated document, job, match, and application lookup to the authenticated owner (including legacy record-ID endpoints).
- Use separate production credentials, secret management, and `DEBUG=false`; remove development database defaults and fail closed on missing mandatory production secrets.
- Add rate limiting, safe error handling, document retention/deletion, backups, audit logs, and a threat-model review.
- Test end-to-end authorization, including cross-user IDOR cases, before any public exposure.

**Scope:** CI-001 only reduces default network exposure and documents the boundary. It does not implement authentication or change matching/benchmark code. The V3.4 governance gates remain unchanged.
