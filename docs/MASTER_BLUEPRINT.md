# Master Product Blueprint & Architectural Reference

> **Comprehensive reference blueprint for the Vehicle Maintenance & Operations Tracker across Local Development, GitHub Versioning, and 24/7 QNAP Container Station / Tailscale Deployment.**

---

## 🏗️ 1. Core Domain Engine & Data Architecture

- **Runtime & Database**: Python 3.11+, FastAPI, SQLModel (SQLAlchemy + Pydantic), SQLite in WAL mode (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`).
- **Fleet & Asset Profiles**: VIN decoding (NHTSA API integration), odometer history, rolling annual/daily usage calculations.
- **Document Compliance**: Registrations, insurance, inspections with dynamic expiration tiers (`ACTIVE`, `EXPIRING_WARNING` <= 30d, `EXPIRING_CRITICAL` <= 7d, `EXPIRED`) and multi-format PDF/image attachments.
- **Predictive Maintenance**: Dual-threshold evaluation (mileage vs. calendar interval, whichever arrives first) with predictive due-date forecasting.
- **External Work Orders & Parts**: Mechanic shop directory, labor rates, procurement tracking (`PLANNED` -> `WAITING_ON_PARTS` -> `COMPLETED`), and automated total cost rollups.
- **Consumables & Fluid Specs**: Direct lookup for oils, filters, wipers, spark plugs, and intelligent ceramic/premium upgrades.
- **Knowledge Base & DIY Guides**: Model quirks, failure points, and step-by-step repair manuals.

---

## 📱 2. Mobile Garage Portal & Physical QR Code Ecosystem

- **Driver's Seat Quick-Portal (`/v/{id}`)**: High-contrast, responsive mobile interface optimized for 1-tap odometer updates and fluid specs lookup.
- **Progressive Web App (PWA)**: Full-screen mobile home screen icons (iOS "Add to Home Screen" & Android "Install App").
- **Multi-Endpoint QR Generator**: `GET /api/v1/vehicles/{id}/qr?base_url=...&format=svg|png` supporting dynamic overrides.
- **Interactive Glovebox Sticker Modal**: Web dashboard modal with 1-click endpoint presets:
  - 🌟 Tailscale MagicDNS (`http://nas6e810d.tail8ba0ff.ts.net:8000`)
  - 🔒 Tailscale Direct IP (`http://100.91.20.86:8000`)
  - 🏠 Local Home LAN (`http://192.168.1.198:8000`)
  - Dedicated print stylesheet optimized for printing 2"x2" physical car door jamb or glovebox stickers.

---

## ☁️ 3. Google Calendar REST API Integration

- **Direct Push & Sync**: Native HTTP client (`httpx`) communicating directly with Google Calendar API v3 (`https://www.googleapis.com/calendar/v3/calendars/{calendarId}/events`).
- **Target Calendar**: Configurable via `GOOGLE_CALENDAR_ID` in `.env` (supports `primary` or dedicated secondary calendar `c_xxx@group.calendar.google.com`).
- **OAuth2 Token Lifecycle**: Offline refresh token flow saves credentials to `data/gcal_token.json`. Automatic background refresh keeps the app authenticated 24/7.
- **Automated Reminders**: Custom reminder overrides attached to all events (30-day, 14-day, and 2-day email & popup alerts).
- **Scheduled Background Sync**: Background scheduler (APScheduler) runs every 6 hours to auto-publish upcoming renewals and service milestones.
- **UI Dashboard Controls**: Live connection badge (`🟢 Connected` / `🟠 Not Authorized`) with 1-click "⚡ Sync All Events to Google Calendar Now".

---

## 🐳 4. 24/7 QNAP Container Station Deployment

- **Container Hardening**:
  - Base: `python:3.11-slim`.
  - Non-privileged user: `appuser:appgroup` (UID 1000).
  - Healthcheck: Probes `/healthz` every 30s.
  - Graceful shutdown: `stop_grace_period: 30s` in Compose ensures clean SQLite WAL flushing during NAS reboots.
- **Host Tailscale Perimeter Security**: Port `8000:8000` routed through host Tailscale exit node without opening any router ports.
- **Persistent Storage**: `/share/Container/vehicle_maintenance/data:/app/data` preserves database records, tokens, and attachments.

---

## 🛠️ 5. Deployment Scripts & Operational Tooling

- **1-Click QNAP Updates (`scripts/update_qnap.sh`)**:
  - Streams updated code from Mac to QNAP using `COPYFILE_DISABLE=1 tar --no-xattrs`.
  - Safely excludes `data/` so live production database is never overwritten.
  - Automatically SCPs `data/gcal_token.json` if authenticated.
  - Executes `sudo docker compose up -d --build` inside a login shell (`/bin/sh -l -c`) with explicit Container Station binary paths exported to prevent `sudo: docker: command not found`.
- **1-Click Google Authenticator (`scripts/auth_google.py`)**:
  - Standalone script on Mac that launches browser, handles consent, and captures OAuth tokens.

---

## 🧪 6. Testing & Quality Assurance

- **Test Suite**: 41 comprehensive pytest tests covering all CRUD, intervals, attachments, authentication, QR generation, and Google Calendar sync endpoints.
- **Execution**:
  ```bash
  .venv/bin/pytest tests -v
  ```
