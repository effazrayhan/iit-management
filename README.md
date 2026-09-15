# IIT Management

Phase 1 of the IIT departmental management system: React, FastAPI, Neon PostgreSQL, Google Sign-In, student email parsing, teacher approval state, and JWT sessions.

## Requirements

- Node.js 20.19+ and npm
- Python 3.12+
- A [Neon](https://console.neon.tech/) account
- A [Google Cloud](https://console.cloud.google.com/) account

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

The backend creates the `users` and `student_profiles` tables on its first successful start. No manual SQL is needed.

Neon reference: [connect from Python](https://neon.com/docs/guides/python) and [pooled connections](https://neon.com/docs/connect/connection-pooling).

## 3. Create the Google client ID

1. Open [Google Auth Platform](https://console.cloud.google.com/auth/overview) and create or select a project.
2. Complete **Branding** with the app name, support email, and developer email.
3. Under **Audience**, choose the audience appropriate for your organization. If the app is in testing, add the IIT accounts that will test it as test users.
4. Open **Clients** → **Create client**.
5. Select **Web application** and name it `IIT Management Web`.
6. Add this **Authorized JavaScript origin**:

```text
http://localhost:5173
```

7. Create the client and copy the client ID. A client secret is not used by this app.
8. Put the same client ID in both variables in `.env`:

```env
GOOGLE_CLIENT_ID=123456789-example.apps.googleusercontent.com
VITE_GOOGLE_CLIENT_ID=123456789-example.apps.googleusercontent.com
```

The frontend receives a Google ID token and the FastAPI backend verifies its signature, issuer, expiry, and audience. No authorized redirect URI is required because the app uses Google's popup callback flow.

Google reference: [create a web client ID](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid) and [verify ID tokens on a backend](https://developers.google.com/identity/sign-in/web/backend-auth).

## 4. Configure `.env`

Generate a session-signing secret:

```bash
openssl rand -hex 32
```

Complete the root `.env`:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require&channel_binding=require
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
JWT_SECRET=paste-the-generated-value

FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

STUDENT_EMAIL_PATTERN=^bsse(?P<batch>\d{2})(?P<roll>\d{2})@iit\.du\.ac\.bd$
STAFF_EMAIL_DOMAIN=iit.du.ac.bd
```

| Variable | Used by | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Backend | Neon PostgreSQL connection |
| `GOOGLE_CLIENT_ID` | Backend | Expected audience while verifying Google ID tokens |
| `JWT_SECRET` | Backend | Signs seven-day application sessions |
| `FRONTEND_URL` | Backend | Allowed CORS origin; do not include a trailing slash |
| `VITE_API_URL` | Frontend | FastAPI base URL; do not include a trailing slash |
| `VITE_GOOGLE_CLIENT_ID` | Frontend | Displays Google Sign-In |
| `STUDENT_EMAIL_PATTERN` | Backend | Extracts the student's batch and roll |
| `STAFF_EMAIL_DOMAIN` | Backend | Permitted staff domain |

The default student policy accepts addresses such as `bsse1501@iit.du.ac.bd`, producing program `BSSE`, batch `15`, and roll `01`. Other `@iit.du.ac.bd` accounts become pending teachers. All other domains are rejected.

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

Open [http://localhost:5173](http://localhost:5173) and sign in with an allowed Google account.

## 6. Run checks

```bash
cd backend && .venv/bin/python -m unittest -v test_email_policy.py
cd ../frontend && npm run build
```

## 7. Deploy to Vercel

Create two Vercel projects from the same GitHub repository. See Vercel's [monorepo setup](https://vercel.com/docs/monorepos), [FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi), and [Vite guide](https://vercel.com/docs/frameworks/frontend/vite).

### Backend project

1. Import `effazrayhan/iit-management` into Vercel.
2. Set **Root Directory** to `backend`.
3. Add these environment variables for Production:

```text
DATABASE_URL
GOOGLE_CLIENT_ID
JWT_SECRET
FRONTEND_URL
STUDENT_EMAIL_PATTERN
STAFF_EMAIL_DOMAIN
```

4. Initially set `FRONTEND_URL` to `http://localhost:5173` and deploy.
5. Copy the backend URL, for example `https://iit-management-api.vercel.app`.

### Frontend project

1. Import the same repository as another Vercel project.
2. Set **Root Directory** to `frontend`; Vercel detects Vite automatically.
3. Add these environment variables for Production:

```env
VITE_API_URL=https://iit-management-api.vercel.app
VITE_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

4. Deploy and copy the frontend URL.

### Connect production URLs

1. In the backend Vercel project, change `FRONTEND_URL` to the frontend production URL and redeploy.
2. In the Google web client, add the frontend production URL to **Authorized JavaScript origins** and save:

```text
https://iit-management.vercel.app
```

3. Open the frontend URL and sign in.

Vite variables are embedded during the frontend build, so redeploy after changing any `VITE_*` value. Keep `JWT_SECRET` stable or existing sessions will be invalidated.

## Troubleshooting

- **`KeyError: DATABASE_URL`**: the root `.env` is missing or the variable is unset in Vercel.
- **Database driver error**: ensure the URL begins with `postgresql+psycopg://`, not `postgresql://`.
- **Google `origin_mismatch`**: add the exact browser origin to Authorized JavaScript origins; include the scheme and port, but no path or trailing slash.
- **Google access blocked during testing**: add the account under Google Auth Platform → Audience → Test users.
- **CORS error**: make `FRONTEND_URL` exactly match the origin shown in the browser address bar, then restart or redeploy the backend.
- **Teacher cannot enter**: expected for now; staff accounts remain `PENDING` until the admin approval endpoint is implemented.
- **Student rejected**: confirm the address matches `STUDENT_EMAIL_PATTERN` exactly.
