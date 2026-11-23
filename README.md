# Career Intelligence

Evidence-driven, **single-user** career decision-support prototype. It helps a candidate review confirmed CV evidence, collect and discover vacancies, inspect matching recommendations, prepare evidence-checked application materials, and track applications.

> **Security boundary:** This project currently has **no authenticated user sessions or multi-user authorization**. Run it only on a trusted local machine. Do not publish the web console or API behind a public reverse proxy. See [Local Deployment Security](docs/LOCAL_SECURITY.md).

For the shortest personal-use setup and an honest release acceptance checklist, see [Local-first personal release](docs/PERSONAL_RELEASE.md). To verify a fresh local installation before relying on it, follow the [step-by-step manual acceptance walkthrough](docs/MANUAL_ACCEPTANCE.md). The repository being public does **not** make the unauthenticated running app safe to host publicly.

## Current capabilities

- Upload PDF/DOCX CVs, inspect extraction output, and confirm a candidate profile.
- Manage confirmed CV profiles and attach profile provenance to discovery, matching, and generated documents.
- Add vacancies manually or discover jobs using a configured external provider; provider access requires an API credential.
- Review matching scores, evidence gaps, recommendations, and application strategy (with documented limitations).
- Generate and validate tailored CVs and cover letters; record application states.
- Run offline testing without external LLM calls.

The **matching/extraction research is not production-validated**. Historical V3.3 analysis found substantial extraction instability; V3.4 is a *specification*, not implemented production logic. Its owner decision register explicitly withholds authorization for certain implementation, adjudication, and provider-call activities. See [V3.4 corrective engineering specification](docs/benchmark/v3_4_corrective_engineering_specification.md) and [owner decision register](docs/benchmark/v3_4_owner_decision_register.md).

## Quick start: trusted local Docker Compose

Requirements: Docker with the Compose plugin.

```sh
git clone https://github.com/Tadeni00/career-intelligence.git
cd career-intelligence
docker compose up --build -d
docker compose ps
```

Open **http://127.0.0.1:4173**. The API is available locally at **http://127.0.0.1:8011/docs**; the database port is **127.0.0.1:5433** by default.

The Compose stack intentionally binds every published port to `127.0.0.1`. It uses a development PostgreSQL credential and pins `AI_PROVIDER=offline`; **it is not a hardened deployment**. No remote model calls are made by the Compose API. External vacancy discovery through JSearch remains unavailable unless `JSEARCH_API_KEY` is explicitly supplied. Review [`.env.example`](.env.example), but never commit real credentials.

To inspect logs or stop:

```sh
docker compose logs --tail=100 api
docker compose down
```

`docker compose down` leaves named volumes intact. Do **not** add `-v` unless intentionally deleting development database/storage volumes.

## Development and verification

Backend: Python 3.12 is used by the API container and CI. The package supports Python 3.11+. PostgreSQL is required for the integration tests; `tests/conftest.py` creates/cleans an isolated `career_test` database, so **never point `TEST_DATABASE_URL` to a database containing valuable data**.

```sh
python -m pip install -e ".[dev]"
# With a disposable PostgreSQL service on localhost:5433:
python -m pytest
ruff check apps packages tests
```

Frontend: Node.js 22 is used in CI.

```sh
cd apps/console
npm ci
npm run lint
npm run build
node --experimental-strip-types src/applicationUrl.test.ts
node --experimental-strip-types src/tailoredCvRouting.test.ts
```

The frontend's Vite development proxy currently targets port 8000, which differs from the Docker API's port 8011. The supported zero-configuration path is the Docker Compose console on port 4173; adjust the development proxy appropriately when developing services outside Compose.

Continuous integration is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml): localhost deployment checks, frontend lint/build/route checks, and Python integration tests with an isolated PostgreSQL service. CI runs the current test suite on every PR; see the live GitHub Actions results for the latest exact count. The historical lint scan still reports 64 existing findings and is *temporarily nonblocking*; new deployment-check lint is blocking. This is tracked in [CI-004](https://github.com/Tadeni00/career-intelligence/issues/4), not considered resolved.

## Repository layout

| Directory | Purpose |
| --- | --- |
| `apps/api/` | FastAPI application, business services and AI-provider integration |
| `apps/console/` | React/TypeScript/Mantine user interface |
| `packages/matching/` | Matching engine and diagnostic utilities |
| `migrations/` | Alembic schema changes |
| `tests/` | Backend tests, including frozen research-contract checks |
| `validation_jobs/` | Validation harness and historical development evidence |
| `docs/benchmark/` | Research artifacts, specifications, decision records |
| `deployment_checks/` | Deployment safety and read-only integrity diagnostics |

## Important limits and privacy

- Authentication, cross-user authorization, production secrets management, document retention and external network protection are **not implemented**. Never deploy for untrusted users in this state.
- The public repository currently contains CV/profile-derived artifacts that may be personal; see [SEC-003](https://github.com/Tadeni00/career-intelligence/issues/3). Removing a file in a later commit does not erase it from Git history.
- Recommendations are decision-support signals, not confirmed hiring outcomes or proof of eligibility. Human review is required before an application.
- Live job-provider calls can consume quota or incur charges. Frozen benchmark tests and their stored evidence should not be rewritten, refreshed, or used to infer authorization for new experiments.
- Two frozen input checksums from the original Windows environment were reconciled to the LF representation in Git without changing the benchmark files. See [CI-002 forensic note](docs/benchmark/ci_002_frozen_artifact_line_endings.md).

## Project direction

The current release target is a trustworthy **personal-use, local-first** career workflow, not multi-tenant hosting. Authentication and user isolation become prerequisites only if public hosting is ever pursued; evidence-backed matching improvements need separate evaluation. Improvements should be incremental and verified through GitHub pull requests; governed V3.4 research activities require their separate approvals.
