# JKOMS Global — Full Stack Package

Real backend, real database, four working frontends. Everything to open in
VS Code and actually run.

## What's in here

- **/backend** — FastAPI + SQLModel + Postgres API. Auth, locations,
  clients, bookings, shipments, containers, uploads, rates/AQE quote
  engine, invoices, payments, documents, notifications. Own README inside
  with full setup steps.
- **/prototypes** — four HTML apps: Command Center, Website (with the AQE
  Quote Engine), Client Portal, JKOMS Field. Open any of them directly in
  a browser.
- **/blueprint** — the master ecosystem write-up (Word doc).

## Fastest path to seeing it work end-to-end

1. **Start the backend.** Open `/backend` in VS Code, follow its README:
   `python -m venv venv` → activate it → `pip install -r requirements.txt`
   → `docker compose up -d` → `cp .env.example .env` → create tables →
   `python seed.py` → `uvicorn app.main:app --reload`.
   Confirm it's up: `http://localhost:8000/health` → `{"status":"ok"}`.
   Try `http://localhost:8000/docs` too — every endpoint is testable by
   hand there before touching the frontend.

2. **Serve the frontend folder** (not double-click — see why in the
   backend README's CORS note):
   ```
   cd prototypes
   python -m http.server 5500
   ```
   Open `http://localhost:5500/JKOMS_Website_AQE.html`.

3. **Get a real quote.** Scroll to "Get Instant Quote," fill it in, submit.
   That's hitting `POST /rates/quote` on your running API. Click "Submit
   Booking Request" and it creates a real row via `POST /bookings/public`.

4. **Check it landed.** In `/docs`, click Authorize, log in with
   `admin@jkomsglobal.com` / `ChangeMe123!` (seed script created this —
   it'll ask you to change the password on first real use), then try
   `GET /bookings`. Your submission is in there.

## Honest status — what's real vs. what's still mock

| Piece | Status |
|---|---|
| Backend API (all 13 routers) | Real, running against Postgres |
| Website — AQE Quote Engine + booking submit | **Live**, calls the real API |
| Command Center — Bookings, Shipments, Containers, Invoices, Documents, Clients | **Live**, after staff login (or "Continue in Demo Mode") |
| Client Portal — My Shipments, Invoices, Documents | **Live**, after client login (or "Continue in Demo Mode") |
| JKOMS Field — My Jobs, scan-to-update, delivery confirmation | **Live**, after courier login (or "Continue in Demo Mode") |
| Command Center — Lockers, Team, Analytics, Settings | Mock data — no backend routes exist for these yet |
| Website — services, coverage, tracking demo section | Mock content |

All four apps now sign in against the real API and pull real data, each
with a graceful "Continue in Demo Mode" fallback if the backend isn't
running. Seeded accounts (`python seed.py`):

| Role | Email | Password |
|---|---|---|
| Staff/Admin | admin@jkomsglobal.com | ChangeMe123! |
| Client | amara@example.com | ClientDemo123! |
| Courier | musa@jkomsglobal.com | CourierDemo123! |

All three are pre-filled in each login screen — just hit Sign In.
The admin login can create `supervisor` and `hr` accounts too, from
Command Center's Team page — those two roles don't have a seeded account
of their own yet since there's no seed data specific to what they'd see.

## A real bug found and fixed in this pass

`Shipment.client_id`, `Booking.client_id`, and `Invoice.client_id` all
point to `clients.id` — a separate business-record table — but the
visibility filters that scope "show me my own stuff" for a client login
were comparing them against `user.id`, which is the `profiles.id` from
the JWT. Different tables, so every client login would have seen **zero**
of their own shipments, bookings, or invoices, and the delivery
confirmation endpoint would 403 on a client's own shipment. Fixed with a
proper `get_own_client_id()` helper in `deps.py` that resolves a client's
real `Client.id` via `Client.profile_id`, used consistently across all
three routers plus `confirm_delivery`. Worth knowing about if you extend
any of these routers further — the same mismatch is easy to reintroduce.

## The full lifecycle loop is now closed

Beyond just reading data, three actions that used to be cosmetic buttons
now actually change the database:

- **Command Center → Bookings → "Convert to Shipment"** — prompts for the
  missing recipient/sender details a booking doesn't capture, then calls
  `POST /shipments` with `from_booking_id` set. The backend marks the
  original booking `converted` and links it to the new shipment.
- **Command Center → shipment drawer → "Assign / Reassign Courier"** —
  calls the new `GET /staff?role=courier` endpoint to list real couriers,
  then `PATCH /shipments/{id}/courier`. Log into JKOMS Field as that
  courier and the job now shows up in their "My Jobs" for real.
- **Command Center → Finance → "Record Payment"** — calls `POST /payments`
  (asks physical/cash vs online first), which updates the invoice's
  paid/partial status automatically, then re-fetches the invoice list.

End-to-end proof: submit a quote on the Website → "Submit Booking
Request" → it lands in Command Center's Bookings → "Convert to Shipment"
→ "Assign Courier" to Musa → log into Field as Musa, the job is there →
scan it through to Delivered → back in Command Center, raise an invoice
and record the payment. One booking, one system, the whole way through.

## Gaps closed in this pass

A big batch of real requests, closed for real rather than faked:

- **Real logo** — your actual JKOMS Global brand mark is now embedded in
  all four apps (nav bars, login screens), replacing the placeholder "JK"
  squares from earlier passes.
- **New roles**: `supervisor` and `hr` added alongside admin, chairman,
  depot_staff, courier, customs_finance, client — with a proper split
  between `STAFF_ROLES` (operational access) and `ADMIN_ROLES` (account
  management), so a supervisor can run operations without being able to
  create or delete logins.
- **Admin can now edit anything after submission.** New
  `PATCH /shipments/{id}` lets admin/supervisor/depot_staff correct a
  package's or vehicle's details — address, weight, recipient, notes,
  service level — at any time, without disturbing the journey-event audit
  trail. Wired into Command Center's shipment drawer as "Edit Shipment
  Details."
- **You can now see and push where a vehicle/package actually is.** The
  shipment drawer has a new "Push to Next Stage →" button — any staff
  member (not just the assigned courier's phone) can move a shipment
  through booking → collection → warehouse → consolidation → transit →
  customs → last mile → delivered, straight from the desktop. This is
  exactly what was missing when a vehicle sat at "waiting for shipment"
  with no way to move it.
- **Account management is now a real admin feature**, not a mock page.
  `POST/GET/PATCH/DELETE /auth/accounts` (admin/chairman only). Command
  Center's Team page has "+ Add Staff Account," Edit, and Delete, all
  wired to the real endpoints.
- **Staff profile photos** — click any real staff member's avatar in the
  Team page to upload a photo (`POST /uploads/avatars`, then saved onto
  their account). Shows up as their actual photo instead of initials from
  then on.
- **A real audit log.** New `AuditLog` table + a `log_audit()` helper,
  wired into account create/edit/delete, shipment edits, and payments —
  the actions worth actually being able to answer "who did that and when"
  about. `GET /staff/audit-log` (admin only), with a live table in Command
  Center's Settings tab. Extending it to more actions is one line per
  action from here, not a redesign.
- **Reconciliation.** Finance now has a live panel: Total Invoiced,
  Collected, Partial, and Outstanding, computed from real invoice data,
  with a built-in "these should add up" sanity note.
- **Analytics got more honest, not just more decorated.** "Shipments by
  Stage" is now a real, live breakdown of your actual shipment data. The
  other three panels (Revenue Trend, Courier Performance, Region Volume)
  are explicitly labeled "demo data" instead of silently pretending to be
  real — because the timestamped history they'd need doesn't exist in the
  schema yet.

## What's still genuinely open

- Photo/signature capture in JKOMS Field's proof-of-delivery sheet is
  still visual only — it doesn't yet upload to `POST /uploads` and attach
  via `POST /documents`. The delivery *event* is real; the photo/signature
  *file* isn't persisted yet.
- "Send Quote" / "Follow Up" on new/quoted bookings (only "Convert to
  Shipment" on a confirmed booking is wired).
- Creating a new container from Command Center, or attaching/detaching
  shipments to one, isn't wired — Containers is read-only live data so far.
- Command Center's Lockers view has no backend routes yet.
- A real HR module (leave, timesheets, reviews) doesn't exist — the `hr`
  role exists for access control, but there's nothing HR-specific to
  access yet.
- Revenue Trend, Courier Performance, and Region Volume in Analytics need
  real historical data (timestamped deliveries, on-time thresholds) before
  they can honestly go live — flagged above, not hidden.

## If something doesn't work

- **CORS error in the browser console** → you opened the HTML file
  directly (`file://...`) instead of through `python -m http.server`. Fix:
  step 2 above.
- **"Could not reach backend" toast** → the API isn't running, or it's on
  a different port than `localhost:8000`. Check the terminal running
  `uvicorn`.
- **`docker compose up -d` fails** → Docker Desktop isn't installed or
  isn't running. Install it, make sure it's open, try again.
