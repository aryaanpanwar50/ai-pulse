# AI Pulse

AI Pulse helps a company understand how well its people use AI at work, team by team.

- **Employees** sign in, pick their organization, and take a short diagnostic. Questions adapt to their job role and seniority. One open-ended answer is scored by an LLM.
- **Each employee** can submit one diagnostic per organization, see a submitted status, open their personal report, and delete that organization's response from the report view if they choose to retake it.
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
# The remaining required settings are documented in .env.example.
alembic upgrade head       # apply versioned schema migrations
python -m app.seed          # resets the local database and creates demo data; password: pulse123
uvicorn app.main:app --reload
```

To build the backend image from the repository root, run `docker build -t ai-pulse-backend ./backend`. The `backend/.dockerignore` file excludes local environment files from the image build context.

The backend requires explicit values for `SECRET_KEY`, `DATABASE_URL`, `AI_MODE`, `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `TOKEN_HOURS`, and `FRONTEND_URL`. There are no application defaults for these settings. The process environment may supply deployment values; local development uses the untracked `backend/.env` file. `FRONTEND_URL` is the single browser origin allowed by CORS. The frontend has its own untracked `frontend/.env` with `VITE_BACKEND_URL`, the API base URL; Vite exposes only variables with the `VITE_` prefix to browser code. `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL` may be empty only when `AI_MODE=mock`.

Migrations are explicit and are not run when the API server starts. For an existing database created by the original app (or by the earlier startup migration), record the legacy schema baseline once, then apply the new revision:

```bash
cd backend
alembic stamp 0001_initial_schema
alembic upgrade head
```

Use `alembic stamp` only for an existing database whose tables already match the original AI Pulse schema. For a fresh database, use `alembic upgrade head` directly.

> **Demo data warning:** `python -m app.seed` drops and recreates every table. Use it only with a disposable local database; do not run it against data you need to keep.

The `0002_diagnostic_submissions` migration preserves older response rows but leaves them unlinked to a submission. Since old rows cannot be reliably grouped into a completed diagnostic, they are excluded from reports and dashboard calculations. New submissions use the versioned submission relationship.

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

| Email | Organization(s) | Role |
|---|---|---|
| asha@northwind.test | Northwind Logistics | Admin |
| meera@bluepeak.test | Bluepeak Retail | Admin |
| ravi@consult.test | Both | Employee at Northwind, admin at Bluepeak |
| priya@northwind.test | Northwind Logistics | Employee (Support) |
| dev@northwind.test | Northwind Logistics | Employee (Engineering, lead) |

## AI mode

`AI_MODE=mock` deterministically samples schema-valid canned responses from `backend/data/mock_ai_responses.json`. The local `.env.example` selects mock mode; the application has no AI mode default. Scores are in the 1–5 range; an empty `flags` list means the answer raised no listed risk. Invalid live model output is rejected without saving a partial submission.

`AI_MODE=live` calls `LLM_API_URL` with `LLM_API_KEY` and `LLM_MODEL`.

## Engineering assessment notes

### What I found and fixed

- The dashboard accepted an `org_id` from the URL but did not check that it matched the organization in the admin's token. The route now rejects a request for another organization, and a regression test covers the cross-organization case.
- The dashboard counted anyone with at least one answer as a respondent and divided answer-score totals by department headcount. It now counts completed submissions and averages each employee's question scores before averaging employees.
- Answers were stored as unrelated rows, so repeat submissions could be confused with one complete diagnostic. A submission now groups one complete role- and seniority-specific answer set per organization membership. Incomplete submissions are rejected and a second submission returns `409` until the existing one is deleted.
- Employees now see a submitted status after organization selection, can open the report, and can delete the response from the report view. Deleting a response removes its report data from subsequent reads.
- The admin dashboard now presents department headcount, response count, average score, maturity level, and top risks in a readable table and list.
- Mock scoring data included malformed results, including out-of-range scores. These fixtures are now schema-valid; malformed model output is still rejected before answers are saved.
- Schema changes are explicit Alembic revisions rather than DDL run when the API starts. See the migration and legacy database instructions above.

### Client request and open questions

- **Small groups:** The five-person privacy threshold is **not implemented yet**. Each department's scores and risks must be hidden or pooled until at least five distinct people have completed the diagnostic. Organization-wide risk totals must also avoid revealing risks from suppressed groups. This remains a rollout blocker.
- **Right to delete:** Employees can delete the response for the currently selected organization after opening its report. The current implementation deletes only the selected organization's data.
- I define a completed diagnostic as every question assigned to that membership's job role and seniority being answered successfully. HR should confirm whether that matches their reporting definition.

### What I deliberately left

- Small-group score and risk suppression/pooling is deferred, so the current admin dashboard is not ready for the client's rollout.
- Passwords still use plain SHA-256 and need modern adaptive hashing before production. JWT signing requires a configured secret of at least 32 bytes, and CORS allows only the configured `FRONTEND_URL`.
- `python -m app.seed` drops and recreates the database. The warning above is intentional; the seeder is for disposable local data only.
- Live model configuration and external-provider data handling have not been hardened beyond output validation. Live mode sends the open-ended answer to the configured endpoint.

### Proposed own feature (not implemented)

I would add a **personal next action** based on the employee's lowest-scoring diagnostic area, with a short explanation tied to the answer that drove it. The current role-based advice can feel generic; this would make the report more actionable for each employee. I would keep the first version deterministic and personal to that employee, without sending more data to the LLM. This feature still needs to be built to satisfy the assessment's own-feature requirement.

### AI tool use

I used AI assistance to inspect the code, propose and implement changes, write tests, and prepare the documentation. One mistake: I added strict validation for AI scores before checking the mock fixtures, which contained a score of `7` and other malformed outputs. That caused a normal mock-mode submission to fail. I caught it with a fixture regression test, removed out-of-range and nonnumeric scores, repaired a missing reason, normalized unsupported risk flags to an empty list, and kept a separate test proving invalid model output is rejected.

### Verification

- Backend: `python -m pytest -q` — 33 tests passed.
- Frontend: `npm.cmd run build` — passed.
- Migration tests cover a fresh database, preservation of legacy answers, and adoption of a database that already has the new schema.
