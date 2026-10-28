# AI Pulse

AI Pulse helps a company understand how well its people use AI at work, team by team.

- **Employees** sign in, pick their organization, and take a short diagnostic. Questions adapt to their job role and seniority. Open-ended answers are scored by an LLM.
- **Each employee** can submit one diagnostic per organization, see a submitted status, open their personal report, and delete that organization's response from the report view if they choose to retake it.
- **Personal reports** include feedback and one to three recommended actions generated at submission time and saved with that submission.
- **Company admins** see a dashboard of AI maturity by department and the top risks across the company.
- Some users (consultants, group-company HR) belong to **more than one organization** and choose one after login.

This codebase was started by a previous developer who has since left. It runs, but it is unfinished, and we are not confident in all of it.

## Stack

- Backend: Python, FastAPI, SQLAlchemy (SQLite by default)
- Frontend: React (Vite)
- AI: any OpenAI-compatible chat completions endpoint, or mock mode with canned responses

## Run it locally

Backend:

```bash
cd backend
pip install -r requirements.txt
# Copy .env.example to .env and set SECRET_KEY to a generated random value.
# Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"
alembic upgrade head       # apply versioned schema migrations
python -m app.seed          # resets the local database and creates demo data; password: pulse123
uvicorn app.main:app --reload
```

The backend requires explicit `SECRET_KEY`, `DATABASE_URL`, `AI_MODE`, `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `TOKEN_HOURS`, and `FRONTEND_URL` settings. There are no application defaults for these settings. `python-dotenv` loads the local `backend/.env`; deployment environment variables take precedence. LLM settings must be present but may be empty in mock mode; live mode requires nonempty values. `SECRET_KEY` must contain at least 32 bytes. CORS accepts only the origin in `FRONTEND_URL`.

Build the API image from the repository root with `docker build -t ai-pulse-backend ./backend`. `backend/.dockerignore` excludes local environment files and database files from that build context. Both backend and frontend `.env` files are ignored by Git; track only their `.env.example` templates.

Migrations are explicit and are not run when the API server starts. For an existing database created by the original app (or by the earlier startup migration), record the legacy schema baseline once, then apply the new revision:

```bash
cd backend
alembic stamp 0001_initial_schema
alembic upgrade head
```

Use `alembic stamp` only for an existing database whose tables already match the original AI Pulse schema. For a fresh database, use `alembic upgrade head` directly.

> **Demo data warning:** `python -m app.seed` drops and recreates every table. Use it only with a disposable local database; do not run it against data you need to keep.

The `0002_diagnostic_submissions` migration preserves older response rows but leaves them unlinked to a submission. Since old rows cannot be reliably grouped into a completed diagnostic, they are excluded from reports and dashboard calculations. New submissions use the versioned submission relationship.

Revision `0003_personal_guidance` adds nullable feedback and next-step fields. Run `alembic upgrade head` before starting the updated API. Existing and seeded submissions retain their scores and risks but have no generated guidance; guidance is created only for new submissions.

Frontend:

```bash
cd frontend
# Copy .env.example to .env and set VITE_BACKEND_URL to the API base URL.
npm install
npm run dev                 # http://localhost:5173
```

Tests:

```bash
cd backend
python -m pytest
```

## Demo accounts (password `pulse123`)

| Email                | Organization(s)     | Role                                     |
| -------------------- | ------------------- | ---------------------------------------- |
| asha@northwind.test  | Northwind Logistics | Admin                                    |
| meera@bluepeak.test  | Bluepeak Retail     | Admin                                    |
| ravi@consult.test    | Both                | Employee at Northwind, admin at Bluepeak |
| priya@northwind.test | Northwind Logistics | Employee (Support)                       |
| dev@northwind.test   | Northwind Logistics | Employee (Engineering, lead)             |

## AI mode

`AI_MODE=mock` uses schema-valid canned scoring responses from `backend/data/mock_ai_responses.json` and deterministic sample guidance. The example environment selects mock mode; the application has no mode fallback. Scores must be in the 1–5 range. Empty risk lists are valid. Invalid scoring output is rejected before answers are saved. Multiple-choice answers currently receive predefined scores only; risk flags come from open-ended answers.

`AI_MODE=live` calls `LLM_API_URL` with `LLM_API_KEY` and `LLM_MODEL`.

## Engineering assessment notes

### What I found wrong and what I fixed

- The dashboard accepted an `org_id` from the URL but did not check that it matched the organization in the admin's token. The route now rejects a request for another organization, and a regression test covers the cross-organization case.
- The dashboard counted anyone with at least one answer as a respondent and divided answer-score totals by department headcount. It now counts completed submissions and averages each employee's question scores before averaging employees.
- The report and dashboard used different maturity thresholds. Both now use `utils.maturity_level`, with cutoffs at 2, 3, and 4. Allowed risk identifiers are also shared by the LLM prompt and validation.
- Risk totals counted repeated flags from one employee more than once. A set now combines flags across that employee's answers, so each employee contributes once per risk.
- Answers were stored as unrelated rows, so repeat submissions could be confused with one complete diagnostic. A submission now groups one complete role- and seniority-specific answer set per organization membership. Incomplete submissions are rejected and a second submission returns `409` until the existing one is deleted.
- Employees now see a submitted status after organization selection, can open the report, and can delete the response from the report view. Deleting a response removes its report data from subsequent reads.
- The admin dashboard's raw JSON placeholder has been replaced by a department table and top-risk list, with loading and error states.
- Mock scoring data included malformed results, including out-of-range scores. These fixtures are now schema-valid; malformed model output is still rejected before answers are saved.
- Schema changes are explicit Alembic revisions rather than DDL run when the API starts. See the migration and legacy database instructions above.
- The known JWT secret fallback and wildcard CORS were removed. Required configuration is validated at startup, and CORS permits only the configured frontend origin, required methods, and required headers.
- Local `.env` files are ignored, the previously tracked backend `.env` was removed from the repository's current tree, and Docker excludes local environment files from the documented build context.
- The Docker command now starts `app.main:app`, matching the package layout.
- Seniority filtering compared words alphabetically. It now uses explicit junior, mid, senior, and lead ranks.
- SQLite connections are reused through the engine pool, with a 30-second lock wait. DB Browser's open transaction caused the local deletion lock; closing it resolved that incident. Increasing the timeout alone does not remove SQLite's concurrency limits.

### How I handled the client's request and what I would ask

- **Small groups:** The five-person privacy threshold is **not implemented yet**. Each department's scores and risks must be hidden or pooled until at least five distinct people have completed the diagnostic. Organization-wide risk totals must also avoid revealing risks from suppressed groups. This remains a rollout blocker.
- **Right to delete:** Employees can delete the selected organization's submission, answers, report data, and personalized guidance themselves after opening the report. Subsequent report and dashboard reads exclude deleted data. An already-open dashboard requires a refresh; other browser sessions do not update automatically.
- **Questions for HR:** Should small departments be hidden or safely pooled under "Other teams"? Does completion mean answering every question assigned to an employee's role and seniority, as the current implementation requires?

### What I deliberately left

- Small-group score and risk suppression/pooling is deferred, so the current admin dashboard is not ready for the client's rollout.
- Password hashing still uses plain SHA-256; upgrading it to an adaptive password hash is deferred.
- `/auth/select-org` still issues a scoped token before checking membership. Protected endpoints check membership, but selection itself should reject unauthorized organizations before issuing a token.
- Provider data handling needs review before production. Live scoring sends open-ended answers; guidance additionally sends the selected diagnostic's questions, answers, scores, flags, job role, and seniority. Names, emails, and other organizations' submissions are not added to the guidance request, but free text may contain sensitive information.

### Your own idea: the problem it solves and why you picked it

**Implemented: personalized feedback and next steps.** Previously, every employee in a role received the same fixed suggestions. A score alone did not explain what that employee could improve. I picked personalized guidance to turn the employee's own answers into a practical learning plan.

After scoring, live mode makes one additional guidance request at submission time with a 20-second timeout. Valid feedback and one to three actions are stored on the submission. Opening the report never calls the model again. Deleting the submission removes its guidance; submitting a new diagnostic generates new guidance. Existing submissions are not backfilled.

Feedback must be nonempty and no longer than 600 characters. There must be one to three nonempty actions, each at most 240 characters. Incorrect types and extra fields are rejected. If the provider times out or returns invalid guidance, the diagnostic still saves and the report shows guidance as unavailable. Mock mode returns clearly labelled, deterministic sample guidance without a network call.

The prompt treats answers as untrusted data, requires advice grounded in self-reported answers, and forbids invented policies, tools, or incidents. Format validation cannot prove factual correctness; employees should review the advice. Guidance cannot overwrite the separate scores or risk flags.

To demonstrate the feature, submit a new diagnostic and open the report. Reopen it to see the same saved feedback. Delete it and submit different answers to obtain fresh guidance. The report displays the feedback without an introductory AI label, and uses plain punctuation instead of em dashes.

### How I used AI tools and one place they got it wrong

I used AI assistance to inspect the code, discuss tradeoffs, implement fixes and the personalized-guidance feature, write regression tests, and prepare documentation. One mistake: AI assistance introduced strict score validation before checking the mock fixtures, which contained a score of `7` and other malformed output. A normal mock submission then failed. A regression test caught it; invalid score examples were removed, valid-score examples were repaired, and a separate test still verifies that invalid model scoring cannot create a partial submission.

### Verification

- Backend: `python -m pytest -q` — 51 tests passed.
- Frontend: `npm.cmd run build` — passed.
- Migration tests cover a fresh database, preservation of legacy answers, and adoption of a database that already has the new schema.
- Local schema verification: `cd backend` then `alembic check` reports no new upgrade operations; the migrated database matches the current models.
- Guidance tests cover generation once at submission, stable report reads, deletion and resubmission, invalid-output rejection, timeout handling, organization isolation, and preservation of older submissions during migration.
- Live guidance was demonstrated manually; automated provider tests use simulated responses and cannot prove the quality of every live model response.

### Implementation file map

| Feature or fix | Files to review |
| --- | --- |
| One complete submission per membership, duplicate-question protection, saved guidance fields | [models.py](backend/app/models.py), [diagnostic.py](backend/app/routes/diagnostic.py) |
| Submission status, atomic answer/submission deletion, permission scoping | [diagnostic.py](backend/app/routes/diagnostic.py), [auth.py](backend/app/auth.py) |
| Saved reports without regeneration, feedback deletion with the submission | [reports.py](backend/app/routes/reports.py), [reporting.py](backend/app/services/reporting.py) |
| Dashboard organization check, completed-employee averages, unique employees per risk | [dashboard.py](backend/app/routes/dashboard.py) |
| Shared maturity thresholds and allowed risk identifiers | [utils.py](backend/app/utils.py), [llm.py](backend/app/services/llm.py), [diagnostic.py](backend/app/routes/diagnostic.py) |
| Mock/live scoring, output parsing, valid mock examples | [llm.py](backend/app/services/llm.py), [scoring.py](backend/app/services/scoring.py), [mock fixtures](backend/data/mock_ai_responses.json) |
| Personalized guidance, strict output validation, optional-failure behavior | [guidance.py](backend/app/services/guidance.py), [diagnostic.py](backend/app/routes/diagnostic.py) |
| Required settings, JWT secret length, single-origin CORS, explicit API URL | [config.py](backend/app/config.py), [main.py](backend/app/main.py), [api.js](frontend/src/api.js), backend/frontend `.env.example` files |
| Explicit migrations and existing-data preservation | [Alembic configuration](backend/alembic.ini), [migration environment](backend/alembic/env.py), [versioned migrations](backend/alembic/versions) |
| Pooled sessions, SQLite lock wait, submission-compatible demo data | [db.py](backend/app/db.py), [seed.py](backend/app/seed.py) |
| Role/seniority question selection | [questions.py](backend/app/services/questions.py) |
| Employee flow, report/delete controls, saved guidance presentation | [App.jsx](frontend/src/App.jsx), [EmployeeFlow.jsx](frontend/src/pages/EmployeeFlow.jsx), [Diagnostic.jsx](frontend/src/pages/Diagnostic.jsx), [Report.jsx](frontend/src/pages/Report.jsx) |
| Department dashboard and responsive table | [Dashboard.jsx](frontend/src/pages/Dashboard.jsx), [styles.css](frontend/src/styles.css) |
| Correct Docker entry point, environment-file exclusion, declared dependencies | [Dockerfile](backend/Dockerfile), [.dockerignore](backend/.dockerignore), [.gitignore](.gitignore), [requirements.txt](backend/requirements.txt) |
| Regression evidence for API behavior, isolation, guidance, migrations, configuration, pooling, and seniority | [backend tests](backend/tests) |

Presence of these changes does not mean the deferred requirements above are complete. In particular, adaptive password hashing, membership validation at organization selection, and small-group privacy suppression are still outstanding.
