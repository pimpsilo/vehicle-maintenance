# Vehicle Maintenance & Operations Tracker

A comprehensive, production-grade vehicle maintenance and operations management system designed for vehicle owners, fleet operators, and automotive enthusiasts.

## 🚀 Key Features

1. **Vehicle Records Management**:
   - Comprehensive vehicle profiles (VIN, Make, Model, Year, Trim, Odometer).
   - Pre-seeded with a **2014 Toyota Avalon XLE Touring (3.5L V6 2GR-FE)**.

2. **Document Tracking & Expiration Alerts**:
   - Tracks State Registrations, Insurance Policies, Smog Inspections, and Warranties.
   - Dynamic status tiers: `ACTIVE`, `EXPIRING_WARNING` (<= 30 days), `EXPIRING_CRITICAL` (<= 7 days), and `EXPIRED`.

3. **Dual-Threshold Maintenance Interval Engine**:
   - Evaluates service thresholds across both **Mileage Interval** (e.g., 10,000 miles) and **Calendar Time** (e.g., 12 months), whichever arrives first.
   - Accrual rate forecasting calculates exact projected calendar due dates using average daily mileage.

4. **External Service & Parts Sourcing Coordinator**:
   - Mechanic shop directory (hourly rates, specialties, contact info).
   - Work order tracking (`PLANNED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`).
   - Sourced parts tracking (OEM part numbers, suppliers like RockAuto, order & shipment tracking).
   - Automatic cost roll-up ($\text{Total Order Cost} = \sum \text{Parts} + \text{Labor}$).

5. **Scheduling & Local Desktop Notifications**:
   - In-process background scheduler (APScheduler) performing periodic checks.
   - Native macOS User Notification Center banners via AppleScript (`osascript`) with smart cooldown deduplication to prevent notification spam.

6. **Google Calendar Integration & Automated Reminders**:
   - Synchronizes confirmed service appointments and document renewal deadlines directly to Google Calendar.
   - Configures automated reminder overrides (popups and emails at 30d/14d/2d for renewals; 24h/2h for service appointments).

7. **Reference Documents & Community DIY Instructions**:
   - Official factory maintenance manuals, fluid capacities, and torque specifications.
   - Step-by-step DIY guides with required tools and instructions from owners who performed maintenance ahead of scheduled intervals (e.g. 2GR-FE intake plenum & rear spark plug removal).

8. **Vehicle Knowledge Base (Quirks & Real-World Intelligence)**:
   - Real-world fuel economy logs (observed MPG vs EPA ratings).
   - Common failure points & technical bulletins (e.g. all-metal oil cooler pipe replacement).
   - Known vehicle quirks (e.g. cold start VVT-i gear rattle, strut mount isolator creak).

9. **Consumable Parts & Fluids Cheat Sheet**:
   - Instant reference for wiper sizes (26"/18"), oil weight & capacity (0W-20, 6.4 qt), tire size & pressure (`215/55R17` @ 33 PSI), fuel grade (87 Octane), spark plugs, and transmission fluid.

10. **QR Code Access & Mobile Quick-Action Portal**:
    - Generates dynamic PNG/SVG QR codes for vehicle glovebox or door jamb stickers.
    - Responsive mobile web interface (`/v/{vehicle_id}`) for fast one-tap odometer updates, consumable cheat-sheet lookups, and quick service logging right from the driver's seat.

---

## 🛠️ Quick Start

### 1. Activate Virtual Environment
```bash
cd vehicle_maintenance
source .venv/bin/activate
```

### 2. Seed Test Vehicle (2014 Toyota Avalon)
```bash
python -m app.seed.seed_avalon
```

### 3. Start the Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Open Interfaces
- **Interactive Swagger UI / API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Mobile Vehicle Portal**: [http://localhost:8000/v/1](http://localhost:8000/v/1)
- **Download Vehicle QR Code (PNG)**: [http://localhost:8000/api/v1/vehicles/1/qr](http://localhost:8000/api/v1/vehicles/1/qr)
- **Download Vehicle QR Code (SVG)**: [http://localhost:8000/api/v1/vehicles/1/qr?format=svg](http://localhost:8000/api/v1/vehicles/1/qr?format=svg)

---

## 🐳 Docker & QNAP NAS Deployment (24/7 Tailscale Access)

The application is fully containerized and optimized for 24/7 self-hosting on **QNAP NAS (QTS / QuTS hero)** via **Container Station**:

- **Pre-built Compose**: Includes [`docker-compose.yml`](docker-compose.yml) and production [`Dockerfile`](Dockerfile) running under non-privileged `appuser`.
- **Zero-Trust Tailscale Integration**: Leverages QNAP's host Tailscale instance and exit node for secure mobile (iOS / Android) and PC remote access with zero open router ports.
- **Dynamic Mobile QR Codes**: Physical vehicle glovebox QR stickers dynamically resolve to your Tailscale MagicDNS or Tailscale IP.
- **Complete Setup Guide**: See [QNAP Deployment Guide](QNAP_DEPLOYMENT_GUIDE.md) for step-by-step instructions on storage pool setup, data migration, and iOS home-screen PWA configuration.

```bash
# Deploy with Docker Compose
docker compose up -d --build
```

---

## 🧪 Running the Test Suite

```bash
pytest tests -v
```
All 39 automated tests verify CRUD operations, dual-threshold math, document expiration statuses, parts cost aggregation, QR code generation, mobile template rendering, calendar sync payloads, dynamic environment configuration, `/healthz` probes, and HTTP Basic Auth enforcement.

