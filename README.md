# IIT Management

IIT departmental management system through Phase 8: authentication, academic data, student profiles, CR elections, classrooms, attendance, complaints, anonymous course feedback, dashboards, donor search, notifications, auditing, and production hardening.

## Requirements

- Node.js 20.19+ and npm
- Python 3.12+
- A [Neon](https://console.neon.tech/) account
- A Gmail or Google Workspace account for verification and reset emails

## 1. Clone the repository

```bash
git clone https://github.com/effazrayhan/iit-management.git
cd iit-management
cp .env.example .env
```

`.env` contains secrets and is ignored by Git. Never commit it.

## 2. Create the Neon database

1. Open the [Neon Console](https://console.neon.tech/) and select **New Project**.
2. Name it `iit-management`, select the closest region, and create it.
3. On the project dashboard, select **Connect**.
4. Enable **Connection pooling** and copy the connection string.
5. Change its scheme from `postgresql://` to `postgresql+psycopg://`, then set `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST-pooler.REGION.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

The backend creates its tables on the first successful start and adds missing Phase 2 fields to an existing Phase 1 database. No manual SQL is needed.

Neon reference: [connect from Python](https://neon.com/docs/guides/python) and [pooled connections](https://neon.com/docs/connect/connection-pooling).

## 3. Configure Gmail SMTP

Use a dedicated Gmail account rather than a personal mailbox.

1. Enable [2-Step Verification](https://support.google.com/accounts/answer/185839) on the sender account.
2. Open [Google App Passwords](https://myaccount.google.com/apppasswords).
3. Create an app password named `IIT Management` and copy its 16 characters.
4. Add the mailbox and app password to `.env`. Do not use the normal Gmail password:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-address@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=your-address@gmail.com
```

The backend uses SSL on port 465. App passwords require 2-Step Verification and might be unavailable on some managed or Advanced Protection accounts. See Google's [app-password guide](https://support.google.com/accounts/answer/185833) and [SMTP settings](https://support.google.com/a/answer/176600).

## 4. Configure `.env`

Generate a session-signing secret:

```bash
openssl rand -hex 32
```

Complete the root `.env`:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require
JWT_SECRET=paste-the-generated-value
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-address@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=your-address@gmail.com

FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000

STUDENT_EMAIL_PATTERN=^bsse(?P<batch>\d{2})(?P<roll>\d{2})@iit\.du\.ac\.bd$
STAFF_EMAIL_DOMAIN=iit.du.ac.bd
SUPER_ADMIN_EMAIL=admin@iit.du.ac.bd
COOKIE_SECURE=false
```

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Backend | Neon PostgreSQL connection |
| `JWT_SECRET` | Backend | Signs seven-day application sessions |
| `SMTP_HOST` / `SMTP_PORT` | Backend | Gmail SMTP connection; defaults to `smtp.gmail.com:465` |
| `SMTP_USER` / `SMTP_PASSWORD` | Backend | Gmail address and app password |
| `SMTP_FROM` | Backend | Sender address; normally the same as `SMTP_USER` |
| `FRONTEND_URL` | Backend | Allowed CORS origin; do not include a trailing slash |
| `VITE_API_URL` | Frontend | FastAPI base URL; do not include a trailing slash |
| `STUDENT_EMAIL_PATTERN` | Backend | Extracts the student's batch and roll |
| `STAFF_EMAIL_DOMAIN` | Backend | Permitted staff domain |
| `SUPER_ADMIN_EMAIL` | Backend | The only email assigned the initial `SUPER_ADMIN` role |
| `COOKIE_SECURE` | Backend | `false` for local HTTP; `true` for production HTTPS cookies |

The default student policy accepts addresses such as `bsse1501@iit.du.ac.bd`, producing program `BSSE`, batch `15`, and roll `01`. `SUPER_ADMIN_EMAIL` becomes the active super admin after email verification. Other `@iit.du.ac.bd` accounts become pending teachers. All other domains are rejected.

Set `SUPER_ADMIN_EMAIL` to your real email before signup. If that address already has a verified account, signing in once upgrades it to `SUPER_ADMIN`.

## 5. Run locally

Start the backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn api.index:app --reload
```

Verify it at [http://localhost:8000/api/health](http://localhost:8000/api/health). API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

In a second terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173), create an account, verify the emailed code, and sign in. Passwords must contain at least eight characters.

Signup verification and the forgot-password wizard email six-digit codes that expire after 10 minutes. Each code has five attempts; password-reset codes can be requested once per minute.

## 6. Run checks

```bash
cd backend && .venv/bin/python -m unittest discover -v
cd ../frontend && npm run build
```

## 7. Use the system

1. Sign up with `SUPER_ADMIN_EMAIL` and verify its OTP.
2. In **Academic setup**, create the program, session, batch, semester, first course, and optional hall. Repeat the form for more courses or batches; existing master records are reused.
3. Teachers sign up and verify their email. The super admin approves them or promotes them to department admin.
4. Students sign up with the configured address format. Their program, batch, and roll are parsed from the email and matched to the configured batch.
5. Teachers create classrooms. Matching students are enrolled automatically; teachers then add class sessions, record attendance, and view anonymous feedback aggregates.
6. Admins create CR positions and elections, then approve candidates and close elections after voting ends. Students nominate themselves and cast one secret ballot per election.
7. Students complete profiles, view attendance, submit one anonymous review per enrolled classroom, and submit complaints. Admins move complaints through the required workflow.
8. Dashboard cards summarize role-specific activity. Students can opt into donor discovery and separately choose whether their phone is visible.
9. Notifications cover account approval, classrooms, attendance, complaints, nominations, and election results. Admins can inspect the audit log.

Interactive endpoint documentation is available at `/docs` on the backend. Authentication uses a seven-day HttpOnly cookie; passwords and tokens are never stored in browser storage.

## 8. Deploy to Vercel

Create two Vercel projects from the same GitHub repository. See Vercel's [monorepo setup](https://vercel.com/docs/monorepos), [FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi), and [Vite guide](https://vercel.com/docs/frameworks/frontend/vite).

### Backend project

1. Import `effazrayhan/iit-management` into Vercel.
2. Set **Root Directory** to `backend`.
3. Add these environment variables for Production:

```text
DATABASE_URL
JWT_SECRET
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_FROM
FRONTEND_URL
STUDENT_EMAIL_PATTERN
STAFF_EMAIL_DOMAIN
SUPER_ADMIN_EMAIL
COOKIE_SECURE
```

4. Initially set `FRONTEND_URL` to `http://localhost:5173` and deploy.
5. Copy the backend URL, for example `https://iit-management-api.vercel.app`.

### Frontend project

1. Import the same repository as another Vercel project.
2. Set **Root Directory** to `frontend`; Vercel detects Vite automatically.
3. Add these environment variables for Production:

```env
VITE_API_URL=https://iit-management-api.vercel.app
```

4. Deploy and copy the frontend URL.

### Connect production URLs

1. In the backend Vercel project, change `FRONTEND_URL` to the frontend production URL and redeploy.
2. Set `COOKIE_SECURE=true` in the backend production environment.
3. Use sibling custom domains such as `app.example.com` and `api.example.com`. This avoids browsers treating the backend session cookie as a third-party cookie.
4. Open the frontend URL, create an account, and test login, logout, email verification, and password reset.

Vite variables are embedded during the frontend build, so redeploy after changing any `VITE_*` value. Keep `JWT_SECRET` stable or existing sessions will be invalidated.

## Production checklist

Before each database-changing deployment:

1. Create a restorable Neon branch or snapshot according to your Neon plan.
2. Deploy against a preview database branch and run `python -m unittest discover -v`.
3. Verify `/api/health`, login, one role-protected endpoint, and the Vercel function logs.
4. Run the dependency-free health load probe:

```bash
cd backend
LOAD_TEST_URL=https://api.example.com/api/health \
LOAD_TEST_REQUESTS=500 LOAD_TEST_CONCURRENCY=20 .venv/bin/python load_test.py
```

5. Pilot with one batch, then a few batches, then teachers, before department-wide access.

Also define the department's retention rules for complaints, feedback, attendance audits, and account deletion; test a Neon restore; rotate SMTP and JWT secrets after exposure; and arrange an independent penetration test before handling real sensitive reports. The built-in auth limiter is per Vercel instance—add a shared Redis-backed limiter when traffic or abuse requires enforcement across instances.

## Troubleshooting

- **`KeyError: DATABASE_URL`**: the root `.env` is missing or the variable is unset in Vercel.
- **Database driver error**: ensure the URL begins with `postgresql+psycopg://`, not `postgresql://`.
- **`Email service is unavailable`**: confirm 2-Step Verification is enabled and `SMTP_PASSWORD` is an app password without spaces, not the Gmail account password.
- **CORS error**: make `FRONTEND_URL` exactly match the origin shown in the browser address bar, then restart or redeploy the backend.
- **Login works locally but not on Vercel**: set `COOKIE_SECURE=true`, ensure frontend requests target HTTPS, and use sibling custom domains so the cookie is first-party/same-site.
- **Teacher cannot enter**: sign in as `SUPER_ADMIN_EMAIL` and approve the request from the dashboard.
- **Student rejected**: confirm the address matches `STUDENT_EMAIL_PATTERN` exactly.
