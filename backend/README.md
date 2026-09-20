# JKOMS Freight OS - Backend (FastAPI)

Custom backend replacing Supabase, built to run fully offline for local
dev/testing and later deploy to a VPS. Implements Phase 1 of the Master
Ecosystem Blueprint: locations, clients, bookings, shipments, journey
events (the unified log - see the big comment at the top of
app/routers/shipments.py for why this fixes the old double-entry risk),
containers, and the schema for invoices/documents/notifications (routes for
those come next).

## Local setup (VS Code, fully offline after first install)

1. Install Python 3.11+ if you don't have it, and Docker Desktop (for the
   local database - no internet needed once images are pulled).

2. Open this folder in VS Code, open a terminal, then:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
   (Windows: venv\Scripts\activate instead of the source line)

3. Start the local database:
   ```
   docker compose up -d
   ```
   Check it's healthy: docker compose ps

4. Environment file:
   ```
   cp .env.example .env
   ```
   The defaults already match docker-compose.yml - no editing needed for
   local dev.

5. Create the database tables. Simplest first-run approach:
   ```
   python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
   ```
   Once past initial setup, switch to Alembic so schema changes are tracked:
   ```
   alembic revision --autogenerate -m "initial schema"
   alembic upgrade head
   ```

6. Run the API:
   ```
   uvicorn app.main:app --reload
   ```
   Opens on http://localhost:8000. Interactive API docs are at
   http://localhost:8000/docs - genuinely useful for testing endpoints by
   hand before the frontend is wired up.

7. Create your first admin account. There's no signup route by design -
   the first account has to be inserted directly. Run this once in a
   Python shell:
   ```python
   import asyncio
   from app.database import engine
   from app.models import Profile, UserRole
   from app.security import hash_password
   from sqlmodel.ext.asyncio.session import AsyncSession

   async def seed():
       async with AsyncSession(engine) as session:
           session.add(Profile(
               email="you@jkomsglobal.com",
               hashed_password=hash_password("ChangeMe123!"),
               full_name="Your Name",
               role=UserRole.admin,
               must_change_password=True,
           ))
           await session.commit()

   asyncio.run(seed())
   ```
   After that, log in via /auth/login, and use /auth/accounts (needs your
   admin token) to create every account from then on.

## Testing it's all working

- GET /health returns {"status": "ok"} - confirms the API is up
- /docs lets you try every endpoint interactively, including auth - click
  "Authorize," log in, then every request in the docs UI carries your
  token automatically

## What's built vs. what's next

Built: auth (JWT, admin-provisioned accounts, forced password change),
locations, clients, bookings (create -> staff review/quote -> convert to
shipment, plus a public no-auth POST /bookings/public for the website),
shipments (create, list, get, assign courier, the unified journey-event
stage updates, two-sided delivery confirmation), containers (create, status
lifecycle, attach/detach shipments), generic file uploads (avatars, proof
of delivery, documents), rates + the AQE quote engine (POST /rates/quote,
public, no auth — this is what the website's quote form calls), invoices,
payments (recording one updates the parent invoice's paid/partial status
automatically), documents (polymorphic attach/list), and a notifications
log (POST /notifications logs the send — no real SMS/WhatsApp provider
wired in yet, see the comment at the top of app/routers/notifications.py).

Not yet built: manifests, vehicles, procurement, and everything else from
the old frontend that wasn't in Blueprint Phase 1.

## Seeding demo data

After the database tables exist (step 5 above), run:

```
python seed.py
```

Creates an admin login (`admin@jkomsglobal.com` / `ChangeMe123!`, forced
password change on first use), the six network locations, per-mode rates,
two demo clients, and one demo shipment — matching what the frontend
prototypes already show as mock data, so wiring them up produces numbers
that line up instead of looking randomly different. Safe to re-run.

## Testing the AQE Quote Engine end-to-end

With the API running (`uvicorn app.main:app --reload`) and seeded:

1. Open `/prototypes/JKOMS_Website_AQE.html` — but not by double-clicking it.
   Browsers block cross-origin fetches from `file://` pages, so serve the
   `/prototypes` folder over a tiny local server instead. From that folder:
   ```
   python -m http.server 5500
   ```
   Then open `http://localhost:5500/JKOMS_Website_AQE.html` in your browser.
   (`.env`'s `CORS_ORIGINS` already includes port 5500 for exactly this.)
2. Scroll to "Get Instant Quote", fill in the form, submit. It calls
   `POST /rates/quote` on the real API — if the API isn't running, it falls
   back to a local estimate and labels it "offline estimate" so it's
   obvious which mode produced the number.
3. Click "Submit Booking Request" on the result — that calls
   `POST /bookings/public` and creates a real row in the bookings table.
   Check it landed: `GET /bookings` in the `/docs` UI (needs your admin
   token — click Authorize first).

## What's still mock data

Command Center, Client Portal, and JKOMS Field (the other three
prototypes) still run on the hardcoded JS arrays from the last build pass —
they aren't fetching from this API yet. The website's Quote Engine and
booking submission above are the first real end-to-end wire-up; the rest
follow the same pattern (fetch on load, same render functions, add a login
step for the ones that need auth) as the next piece of work.

## Deploying later (VPS)

Not covered yet - this README gets a "Production Deployment" section once
we're past local testing. Short version for planning: same Docker Compose
approach but pointing at a managed or self-hosted Postgres, running behind
a reverse proxy (Caddy or nginx) for HTTPS, with Alembic migrations run as
part of deploy rather than init_db().
