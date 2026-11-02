# ATLAS
### Sunucu Envanter Sistemi — Server Inventory System

> Built for OSTIM Teknik Üniversitesi infrastructure management.

---

## Overview

**ATLAS** is a desktop application for managing Proxmox server infrastructure, NAS storage devices, and virtual machines. It provides a dark-themed interface for browsing server credentials, system resources, and VM allocations, stored in local SQLite or a shared remote ATLAS backend. SQLite files and exported backups are **not encrypted**.

---

## Features

- **Login Screen** — Branded authentication portal before accessing inventory
- **Server Inventory** — 8 Proxmox servers and 6 NAS storage devices with full credential management
- **VM Inventory** — 60+ virtual machines with allocated RAM, vCPU, disk, and NIC info
- **System Resources** — Physical server specs: CPU model, sockets, threads, total RAM, kernel, PVE version, boot mode, storage pools
- **Add / Edit / Delete** — Full CRUD for servers and VMs via polished dialogs
- **Password Management** — Masked passwords with show/hide toggle and one-click copy
- **Real-time Search** — Filter servers and VMs instantly (Ctrl+F)
- **Status Indicators** — Green/red dots for running/stopped VM state
- **About Dialog** — Brand info and developer credit
- **Right-click Context Menu** — Edit, delete, add VM directly from the tree
- **Keyboard Shortcuts** — Ctrl+F (search), Ctrl+N (add server), F5 (refresh)
- **Memory / Inventory Backup** — Portable JSON export or a complete local SQLite snapshot, plus automatic daily startup snapshots
- **Import** — Preview and validate JSON/SQLite backups, merge without overwriting existing records, or replace inventory with an automatic recovery copy
- **Remote Backend** — Share inventory through an authenticated HTTP API, with HTTPS required for remote hosts

---

## Screenshots

> Dark themed two-panel layout — server tree on the left, detail view on the right.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language  | Python 3.10+ |
| GUI       | PySide6 (Qt6) |
| Database  | SQLite 3 |
| Styling   | Qt Style Sheets (QSS) |
| Build     | PyInstaller |

---

## Default Credentials

```
Username : admin
Password : atlas2024
```

> Change the password by updating the `users` table in `inventory.db`.

---

## Installation

### Run from source

```bash
# Clone the repository
git clone https://github.com/spedatox/atlas.git
cd atlas

# Install dependencies
pip install PySide6

# Run
python main.py
```

## Memory backups and import

Here, “memory” means the saved inventory: servers, storage devices, VMs, access credentials, resources, and notes.

In the **Dosya** menu:

- **Bellek / Envanter Yedeği Al…** saves a portable `.json` file. In local mode, the file type selector also offers a complete `.db` snapshot, including login users. SQLite's backup API captures committed data consistently, including databases using WAL mode.
- **Envanter İçe Aktar…** accepts ATLAS `.json`, `.db`, `.sqlite`, or `.sqlite3` files up to 50 MiB. It validates the complete inventory and shows record counts and the destination before making changes.

**Birleştir (merge)** adds missing records. Servers match by exact name; VMs match by destination server and VM ID, or by name when VM ID is absent. Existing values are preserved. Reimporting the same file adds no duplicates.

**Değiştir (replace)** replaces all server and VM records in one transaction and asks for an additional confirmation. Database IDs may change; VM relationships are remapped. Login users are preserved in both modes, including when importing a SQLite file. To undo an import, import its recovery `.db` file with **replace**.

Before every import, ATLAS creates a complete SQLite recovery copy in `backups/` beside the active database. Backup failure prevents the import. Existing databases also receive one startup snapshot per day, before any schema migration. Old schemas gain missing columns without dropping inventory tables. Snapshots are retained until an operator removes them; monitor available disk space.

JSON files omit application login users but include inventory access passwords. SQLite snapshots include both. Store these files and the database in a private directory. A full offline recovery of users requires stopping ATLAS/the API, preserving the current database and any WAL files, and restoring a complete SQLite snapshot; normal UI import intentionally restores inventory only.

## Remote backend

`server.py` runs the same SQLite storage behind a versioned API. It uses only Python's standard library; the server does not need Qt. A new remote database starts empty and requires an explicitly configured admin password. Existing database users continue to work.

For a local development server in PowerShell:

```powershell
# Keep this token to configure the desktop client. Do not commit secrets.
$env:ATLAS_API_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:ATLAS_ADMIN_PASSWORD = 'choose-a-strong-initial-password'
python server.py --host 127.0.0.1 --port 8765 --database ./data/inventory.db
```

Launch the desktop in another terminal. On the login screen, choose **Veri Kaynağı / Uzak Sunucu**, select **Uzak ATLAS sunucusu**, enter `http://127.0.0.1:8765` and the same API token, test the connection, and save. Then log in as `admin` using the server's configured password. API tokens are held in memory; provide `ATLAS_API_TOKEN` in the desktop environment to avoid reentering it after a restart.

For access from other machines, run the API bound to loopback behind an HTTPS reverse proxy. For example, a Caddy site can forward to the API:

```caddyfile
atlas.example.com {
    reverse_proxy 127.0.0.1:8765
}
```

Use the HTTPS address in clients, keep the backend port private, and run the server under a service supervisor using a restricted account and persistent database/backup directories. The bundled HTTP server supplies the application API; the reverse proxy supplies TLS and connection/request limits. Configure a proxy request body limit of at most 50 MiB. Plain HTTP clients are allowed only for `localhost`, `127.0.0.1`, or `::1`; TLS verification stays enabled and redirects are rejected.

The API token must contain at least 32 non-whitespace ASCII characters. All requests require it; inventory access also requires a login session. Sessions expire after 12 hours and are invalidated when the service restarts. Restart the desktop to log in again. Failed connections surface an error and never silently switch to local storage. Press **F5** to fetch changes from other clients. Simultaneous edits of one record use the last committed update; imports hold a SQLite write lock across the recovery snapshot and transaction.

Local and remote data sources are independent. To move data, export a JSON backup from one source, restart the desktop, select the other source on the login screen, and import it. Remote exports download portable JSON; recovery `.db` files stay on the server. Imports never transfer or replace login accounts.

### Configuration

| Variable | Purpose |
| --- | --- |
| `ATLAS_BACKEND` | `local` or `remote`; overrides the saved mode at startup |
| `ATLAS_REMOTE_URL` | API base URL, optionally with a reverse proxy path prefix |
| `ATLAS_API_TOKEN` | Shared API secret for server and clients; never written to desktop settings |
| `ATLAS_ADMIN_PASSWORD` | Initial `admin` password when creating an empty server user table |
| `ATLAS_DB_PATH` | Desktop local SQLite path; default is `inventory.db` beside source / the executable, with existing bundled databases detected |
| `ATLAS_CONFIG_PATH` | Optional desktop settings file path |

Desktop settings store only mode and URL, normally at `%APPDATA%/ATLAS/settings.json` on Windows or `~/.config/ATLAS/settings.json` elsewhere. Server CLI options are `--host`, `--port`, `--database`, and `--backup-dir`.

### API routes

All routes are under `/api/v1/` and accept/return JSON. Send `Authorization: Bearer <API token>`. Except for `health` and `login`, also send `X-Atlas-Session: <session>` returned by login. These credentials grant full inventory access; there is no read-only role.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `health` | Service/version check |
| POST | `login` | `{username, password}` → `{session}`; failed credentials return a null session |
| GET | `inventory` | Servers with nested VMs |
| GET | `servers/{id}`, `vms/{id}` | Read a record |
| POST | `servers`, `vms` | Create a record → `{id}` |
| PUT | `servers/{id}`, `vms/{id}` | Update supplied fields, preserve omitted fields |
| DELETE | `servers/{id}`, `vms/{id}` | Delete; server deletion also removes its VMs |
| GET | `backup` | Download portable inventory document |
| POST | `backup` | Create a full snapshot on the server → `{backup_path}` |
| POST | `import` | `{document, mode: "merge" or "replace"}` → counts and recovery backup path |

### Verification

```bash
python -m unittest discover -s tests -v
```

Storage and API tests use temporary databases and an actual loopback HTTP server. Qt tests run headlessly when PySide6 is installed, covering login, local/remote loading, backup menus, import preview, and detail refresh. They skip when Qt is unavailable. No tests access production inventory.

### Windows EXE (build from source)

```bat
# On a Windows machine with Python 3.10+ installed:
build_windows.bat
# Output: dist\ATLAS\ATLAS.exe
```

### Windows EXE (via GitHub Actions)

Push to GitHub — the workflow at `.github/workflows/build-windows.yml` automatically builds the `.exe` and makes it available as a downloadable artifact under the **Actions** tab.

---

## Project Structure

```
atlas-server-inventory/
├── main.py          # Entry point — shows login then main window
├── login.py         # Login window
├── ui_main.py       # Main window, tree, detail panels, CRUD actions
├── database.py      # SQLite schema, seed data, CRUD methods, auth
├── inventory_io.py  # Versioned portable backups, validation, atomic export
├── backends.py      # Storage selection, settings, remote API client
├── server.py        # Authenticated shared inventory API
├── storage_dialogs.py # Data source configuration and import preview
├── tasks.py         # Background storage operations for Qt
├── tests/           # Storage, API, and headless desktop integration tests
├── dialogs.py       # Add/Edit server & VM dialogs, About dialog
├── styles.qss       # Full dark theme (Qt Style Sheets)
├── atlas.spec       # PyInstaller build spec
├── build_windows.bat# One-click Windows build script
└── .github/
    └── workflows/
        └── build-windows.yml  # GitHub Actions Windows build
```

---

## Developer

**Ahmet Erol Bayrak**
OSTIM Teknik Üniversitesi

---

## License

Private — internal use only.
