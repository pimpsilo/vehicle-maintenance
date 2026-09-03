# QNAP NAS Deployment & 24/7 Tailscale Operations Guide

This guide provides step-by-step instructions to migrate and run the **Vehicle Maintenance & Operations Tracker** on your **QNAP NAS (QTS / QuTS hero)** inside **Container Station (Docker)** using your existing **Tailscale** installation (functioning as an exit node / mesh VPN) for 24/7 mobile and PC access.

---

## 🏛️ System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                PRIVATE TAILSCALE TAILNET                                |
|                        (WireGuard Mesh VPN & QNAP Host Exit Node)                       |
+-----------------------------------------------------------------------------------------+
           |                                                                |
           v                                                                v
+-----------------------+                                        +----------------------+
|   Mobile Smartphone   |                                        |    Desktop PC / Mac  |
|  (iPhone / Android)   |                                        |  (Tailscale Client)  |
|  - QNAP Exit Node On  |                                        |  - Web Dashboard     |
|  - Camera QR Scan     |                                        |  - Service Orders    |
|  - One-Tap Log Odo    |                                        |  - Calendar Sync     |
|  - Home Screen PWA    |                                        |  - Parts Directory   |
+-----------------------+                                        +----------------------+
           |                                                                |
           | http://<QNAP-Tailscale-Name>:8000 OR http://100.x.y.z:8000     |
           +-------------------------------+--------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                    QNAP NAS (QTS 5.x+)                                  |
|                                                                                         |
|  +-----------------------------------------------------------------------------------+  |
|  | Host OS (QTS): Tailscale Daemon                                                   |  |
|  | - Connected to Tailnet: <qnap-hostname>.your-tailnet.ts.net                       |  |
|  | - Tailscale IP: 100.x.y.z                                                         |  |
|  | - Functions as Exit Node / Subnet Router                                          |  |
|  +-----------------------------------------------------------------------------------+  |
|                                          |                                              |
|                                          | (Port 8000:8000 Forwarding)                  |
|                                          v                                              |
|  +-----------------------------------------------------------------------------------+  |
|  | Container Station (Docker Container: vehicle-tracker)                             |  |
|  | - Python 3.11-slim, unprivileged user (appuser UID 1000)                          |  |
|  | - FastAPI + SQLModel + APScheduler (24/7 background interval engine)              |  |
|  | - Healthcheck: GET /healthz                                                       |  |
|  | - stop_grace_period: 30s (clean SQLite WAL flush on shutdown)                     |  |
|  +-----------------------------------------------------------------------------------+  |
|                                          |                                              |
|                                          v                                              |
|                 /share/Container/vehicle_maintenance/data                               |
|                 (Persistent SQLite Database + Uploaded Invoices/Attachments)            |
+-----------------------------------------------------------------------------------------+
```

---

## 📋 Prerequisites

1. **QNAP NAS** running QTS 5.0+ or QuTS hero 5.0+.
2. **Container Station 3.x** installed from QTS App Center.
3. **Tailscale** installed and connected on the QNAP host, configured as an exit node.
4. **Tailscale Client** installed on your smartphone (iOS / Android) and PC / Mac.

---

## 🚀 Step 1: Prepare Storage Folder on QNAP

1. Open **File Station** in the QTS Web Desktop.
2. Navigate to your storage volume (usually `CACHEDEV1_DATA` or the standard `Container` share).
3. Create the persistent application data directory:
   ```text
   /share/Container/vehicle_maintenance/data
   ```
   *(Ensure read/write permissions are granted to the Container Station administrator).*

---

## 💾 Step 2: Migrate Your Existing Database & History

To carry over all your existing vehicle records, maintenance history, parts orders, and uploaded documents from your local Mac to the NAS:

### Using SCP / Rsync from your Mac Terminal:
```bash
# Navigate to your project folder
cd /Users/matthewhope/github_projects/vehicle_maintenance

# Copy the SQLite database to your QNAP NAS (using your local LAN IP or Tailscale IP)
scp -r data/vehicle_maintenance.db admin@192.168.1.198:/share/Container/vehicle_maintenance/data/
```
*(If you have other uploaded receipts or attachments in `data/`, transfer them as well).*

---

## 🛠️ Step 3: Configure Environment Variables (`.env`)

In your deployment directory on the NAS (or in the Container Station application setup), create a `.env` file based on `.env.example`:

```env
# Network URL - Configured for your specific QNAP & Tailnet endpoints:
# Option A (Tailscale MagicDNS - Recommended for 24/7 access):
BASE_PUBLIC_URL=http://nas6e810d.tail8ba0ff.ts.net:8000
# Option B (Tailscale Direct IP):
# BASE_PUBLIC_URL=http://100.91.20.86:8000
# Option C (Local LAN IP when using QNAP Exit Node):
# BASE_PUBLIC_URL=http://192.168.1.198:8000

DATA_DIR=/app/data

# Optional Defense-in-Depth Authentication (default: false)
ENABLE_AUTH=false
AUTH_USERNAME=admin
AUTH_PASSWORD=changeme_to_a_strong_password

# Notification Cooldown (hours)
NOTIFICATION_COOLDOWN_HOURS=24
```

> **Why `BASE_PUBLIC_URL` matters**: This URL is dynamically encoded into the printable vehicle QR codes. When you scan the QR sticker on the car door jamb, your phone opens this exact address.

---

## 🐳 Step 4: Deploying via Container Station

### Method A: Using QTS Container Station GUI (No SSH required)

1. Open **Container Station** from the QTS desktop.
2. Click **Applications** in the left sidebar $\rightarrow$ click **Create** (top right).
3. Application Name: `vehicle-maintenance`.
4. Paste the contents of [`docker-compose.yml`](file:///Users/matthewhope/github_projects/vehicle_maintenance/docker-compose.yml):
   ```yaml
   version: '3.8'

   services:
     vehicle-tracker:
       build: https://github.com/pimpsilo/vehicle-maintenance.git#main
       image: vehicle-maintenance:latest
       container_name: vehicle-tracker
       restart: unless-stopped
       ports:
         - "8000:8000"
       environment:
         - DATA_DIR=/app/data
         - BASE_PUBLIC_URL=http://<QNAP_TAILSCALE_IP>:8000
         - ENABLE_AUTH=false
         - NOTIFICATION_COOLDOWN_HOURS=24
       volumes:
         - /share/Container/vehicle_maintenance/data:/app/data
       stop_grace_period: 30s
   ```
5. Click **Create / Validate**. Container Station will build and launch the container.

---

### Method B: Using QNAP SSH Terminal (Fast & Direct)

1. SSH into your QNAP NAS:
   ```bash
   ssh admin@192.168.1.198
   ```
2. Clone or copy your project repository:
   ```bash
   cd /share/Container/vehicle_maintenance
   git clone https://github.com/pimpsilo/vehicle-maintenance.git app-src
   cd app-src
   cp .env.example .env
   # Edit .env with nano or vi
   nano .env
   ```
3. Launch the container in the background:
   ```bash
   docker compose up -d --build
   ```
4. Verify the container is running and healthy:
   ```bash
   docker ps
   curl -f http://localhost:8000/healthz
   ```
   *(Should return `{"status":"healthy","version":"1.0.0"}`).*

---

## 📱 Step 5: Mobile Smartphone Experience (iOS & Android)

### 1. Tailscale Setup on Mobile
- Install the official **Tailscale** app from the App Store or Google Play.
- Log into your Tailnet account.
- **Enable Exit Node**: In the Tailscale app, tap the three dots $\rightarrow$ **Exit Nodes** $\rightarrow$ select your **QNAP NAS**.
- *(Optional)* In iOS/Android Settings, toggle **Connect On Demand / Always-On VPN** so you never have to remember to connect manually.

### 2. Add to Smartphone Home Screen (PWA Experience)
1. In Safari (iOS) or Chrome (Android), navigate to:
   `http://nas6e810d.tail8ba0ff.ts.net:8000/v/1`
2. **iOS**: Tap the **Share** button (box with arrow) $\rightarrow$ select **Add to Home Screen**.
3. **Android**: Tap the three vertical dots $\rightarrow$ select **Install app** or **Add to Home screen**.
4. You now have a standalone vehicle maintenance app icon on your phone that launches directly into your car's mobile portal.

### 3. Glovebox / Door Jamb QR Code
1. On your desktop browser, navigate to the Dashboard and click **🔲 QR Sticker** or open:
   `http://nas6e810d.tail8ba0ff.ts.net:8000/api/v1/vehicles/1/qr`
2. The modal lets you preview, switch endpoints (MagicDNS, Tailscale IP `100.91.20.86`, or Local LAN `192.168.1.198`), and print a 2"x2" physical car sticker.
3. Affix it inside the driver's door jamb, glovebox, or fuel door.
4. Whenever you step out of the car, open your phone camera and scan the sticker: it opens `/v/1` immediately to log current mileage or look up oil/wiper specs.

---

## 💻 Step 6: Desktop PC & Mac Access

1. Ensure the Tailscale client is active in your Mac menubar or Windows system tray.
2. Bookmark `http://nas6e810d.tail8ba0ff.ts.net:8000/dashboard` (or `http://192.168.1.198:8000/dashboard` when at home).
3. **QTS Desktop Icon (Optional)**:
   - In QTS, open **Control Panel** $\rightarrow$ **Custom URL Shortcut**.
   - Title: `Vehicle Maintenance`.
   - URL: `http://localhost:8000/dashboard`.
   - Icon: Upload vehicle icon.
   - Now you can click the app directly from your QNAP desktop dashboard.

---

## 🛡️ Step 7: 24/7 Reliability, Security & Backups

### 1. Zero Router Port Forwarding
Because access is mediated entirely over Tailscale's encrypted WireGuard tunnels and local LAN:
- **No ports are opened on your home router / firewall**.
- Shodan, port scanners, and internet bots cannot see or reach your application.

### 2. Clean Shutdowns & SQLite WAL Safety
In [`docker-compose.yml`](file:///Users/matthewhope/github_projects/vehicle_maintenance/docker-compose.yml), `stop_grace_period: 30s` is configured. When QNAP restarts or powers down, Docker sends `SIGTERM` to Uvicorn, which drains active HTTP requests and checkpoints the SQLite WAL journal (`.db-wal` $\rightarrow$ `.db`) safely before terminating.

### 3. Automated Zero-Downtime Backups
In QTS:
- Open **Snapshot Manager** or **Hybrid Backup Sync (HBS 3)**.
- Create a recurring daily backup schedule for `/share/Container/vehicle_maintenance/data`.
- Since SQLite in WAL mode allows concurrent read snapshots, HBS 3 can backup your database to an external USB drive or cloud backup (Google Drive, Backblaze B2) without stopping the container.

### 4. Updating the Application in the Future
When updates are committed:
```bash
cd /share/Container/vehicle_maintenance/app-src
git pull origin main
docker compose up -d --build
```
Your persistent vehicle records, logs, and attachments in `/share/Container/vehicle_maintenance/data` remain untouched.
