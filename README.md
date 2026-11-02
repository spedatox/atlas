# ATLAS
### Sunucu Envanter Sistemi — Server Inventory System

> Built for OSTIM Teknik Üniversitesi infrastructure management.

---

## Overview

**ATLAS** is a desktop application for managing Proxmox server infrastructure, NAS storage devices, and virtual machines. It provides a clean, dark-themed interface for browsing server credentials, system resources, and VM allocations — all stored locally in an encrypted SQLite database.

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
git clone https://github.com/YOUR_USERNAME/atlas-server-inventory.git
cd atlas-server-inventory

# Install dependencies
pip install PySide6

# Run
python main.py
```

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
