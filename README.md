# tg_queue_mgmt — Telegram Bot Queue Management System

A full-featured **Queue / Token Management System** built with:

- **Python** + **python-telegram-bot v20+** (async)
- **FastAPI** web server with **Server-Sent Events** for real-time updates
- **SQLite** via `aiosqlite` — no external database needed
- Browser **TTS** (Web Speech API) + **beep audio** on every token call

---

## Features

| Feature | Details |
|---|---|
| 📺 **Live Display Page** | Full-screen TV-ready token board with NOW SERVING banner, per-counter status, waiting list, clock, TTS read-aloud, and beep sound |
| 🤖 **Admin Bot Interface** | Add/rename/remove counters, open/close counters, Next/Previous/Recall/Current/Waiting token operations via inline keyboards |
| 🎫 **Customer Token Web Form** | `/take` page — enter name, select department, optional purpose → get token number + live tracking link |
| 📍 **Token Tracker Page** | `/track/<id>` — live-updating page showing position in queue and current serving token |
| 📲 **QR Code Generation** | `/qr` bot command generates a QR PNG pointing to the `/take` page |

---

## Project Structure

```
tg_queue_mgmt/
├── bot/
│   ├── main.py            # Entry point: runs bot + web server concurrently
│   ├── keyboards.py       # Inline keyboard builders
│   └── handlers/
│       ├── admin.py       # Admin commands and inline callbacks
│       └── customer.py    # Customer /start command
├── web/
│   ├── app.py             # FastAPI app with SSE /events endpoint
│   └── static/
│       ├── index.html       # TV display page
│       ├── style.css        # Dark-theme styles
│       ├── take.html        # Customer token-take form
│       ├── track.html       # Customer token-tracking page
│       ├── staff_login.html # Staff login page
│       └── staff_dashboard.html  # Staff counter operations dashboard
├── db/
│   └── database.py        # DB init + all CRUD helpers (aiosqlite)
├── setup.sh               # One-shot setup (venv + deps + .env)
├── run.sh                 # Start the bot + web server
├── Makefile               # Convenience shortcuts
├── .env.example
├── requirements.txt
└── README.md
```

---

## Setup

> Works on **any Linux distro** (Debian, Ubuntu, Arch, Fedora) and **WSL** (WSL1/WSL2 on Windows).

### Prerequisites

You only need **Python 3.9+** and **git**. The setup script handles everything else.

```bash
# Debian / Ubuntu / WSL (Ubuntu)
sudo apt-get install -y git python3 python3-venv python3-full

# Arch Linux
sudo pacman -S git python

# Fedora / RHEL
sudo dnf install -y git python3 python3-virtualenv
```

### 1. Clone

```bash
git clone https://github.com/aman5z/tg_queue_mgmt.git
cd tg_queue_mgmt
```

### 2. Run setup (one command)

```bash
bash setup.sh
```

This will:
- Detect your Python installation
- Auto-install `python3-venv` if missing (on apt/dnf/pacman systems)
- Create a `./venv` virtual environment
- Install all dependencies from `requirements.txt`
- Copy `.env.example` → `.env` if not already present

### 3. Configure `.env`

```bash
nano .env
```

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | recommended | Comma-separated Telegram user IDs with admin access. Leave empty to grant all users admin access (not recommended for production) |
| `BASE_URL` | optional | Public URL of this server (default `http://localhost:8000`) |
| `PORT` | optional | Web server port (default `8000`) |
| `SECRET_KEY` | ✅ | Secret used to sign staff dashboard session cookies. The app will fail to start if this is missing |
| `SESSION_COOKIE_SECURE` | optional | Set `true` in HTTPS deployments so the staff session cookie is sent only over TLS (default `false`) |
| `DB_PATH` | optional | Path to the SQLite database file (default `queue.db` in the working directory) |

> **Tip:** To get your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

### 4. Run

```bash
bash run.sh
# or
make run
```

This starts both the Telegram bot (long-polling) and the FastAPI web server on port 8000.

---

## Usage

### Admin Bot Commands

| Command | Description |
|---|---|
| `/counters` | List all counters with inline management buttons |
| `/addcounter <name>` | Create a new counter |
| `/renamecounter <id> <name>` | Rename a counter |
| `/removecounter <id>` | Delete a counter |
| `/opencounter <id>` | Open a counter |
| `/closecounter <id>` | Close a counter |
| `/status` | Overall queue status |
| `/resetqueue` | Clear all queues (with confirmation) |
| `/qr` | Generate QR code for the token-take page |
| `/users` | List all staff users |
| `/adduser <username> <password> [display_name]` | Create a staff user |
| `/removeuser <username>` | Remove a staff user |
| `/setpassword <username> <new_password>` | Change staff password |
| `/assigncounters <username> <counter_id,...>` | Assign counters to staff |
| `/deactivateuser <username>` | Disable staff login |
| `/activateuser <username>` | Re-enable staff login |
| `/help` | Command reference |

**Inline keyboard actions** (via `/counters`):
- ⏭ **Next** — advance to the next waiting token
- ⏮ **Previous** — revert to the previous token
- 🔁 **Recall** — re-announce the current token (triggers TTS + beep on display)
- 🔢 **Current** — show current token details
- 📋 **Waiting** — list waiting tokens
- 🟢/🔴 **Open/Close** — toggle counter status

### Customer Flow

1. Customer scans QR code or visits `http://<your-host>/take`
2. Enters name, selects department, optional purpose → submits
3. Receives their token number and a link to `/track/<id>`
4. Tracking page auto-refreshes every 5 seconds showing position in queue

### Display Page

Open `http://<your-host>/` on a large screen or TV. The page:
- Connects via SSE and updates instantly when a token is called
- Shows the **NOW SERVING** token in large text
- Reads aloud: *"Token [number], please proceed to [Counter name]"*
- Plays a beep sound on every update
- Shows per-counter status and the full waiting list

### Staff Dashboard

1. Create a staff user in Telegram:
   - `/adduser staff1 pass123 Staff One`
2. Optionally assign counters:
   - `/assigncounters staff1 1,2`
   - Leave assignments empty to allow all counters.
3. Open `http://<your-host>:8000/staff` and log in.
4. Staff can call next/previous/recall tokens and toggle open/close for their assigned counters.

---

## REST API Reference

All API endpoints are served by the FastAPI web server on port 8000.

### Public Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | TV display page (full-screen token board) |
| `GET` | `/take` | Customer token-take form |
| `GET` | `/track/<id>` | Live token tracking page for a specific token |
| `GET` | `/events` | SSE stream — real-time status updates for the display page |
| `GET` | `/api/counters` | JSON list of all counters with `id`, `name`, and `status` |
| `POST` | `/api/token` | Take a new token. Body: `{"name": str, "counter_id": int, "purpose": str\|null}` |
| `GET` | `/api/track/<id>` | JSON tracking info for a token: position, status, current serving number |

### Staff Endpoints (session cookie required)

| Method | Path | Description |
|---|---|---|
| `GET` | `/staff/login` | Staff login page |
| `POST` | `/staff/login` | Submit login credentials (form-encoded `username` + `password`) |
| `GET` | `/staff/logout` | Log out and clear session cookie |
| `GET` | `/staff` | Staff dashboard (redirects to login if not authenticated) |
| `GET` | `/api/staff/counters` | JSON list of counters the logged-in staff member can operate |
| `GET` | `/api/staff/status` | Full queue status snapshot |
| `POST` | `/api/staff/token/next` | Call the next token. Body: `{"counter_id": int}` |
| `POST` | `/api/staff/token/prev` | Revert to the previous token. Body: `{"counter_id": int}` |
| `POST` | `/api/staff/token/recall` | Recall (re-announce) the current token. Body: `{"counter_id": int}` |
| `POST` | `/api/staff/counter/toggle` | Toggle a counter between open/closed. Body: `{"counter_id": int}` |

---

## Quick Reference (WSL)

```bash
# First time
git clone https://github.com/aman5z/tg_queue_mgmt.git
cd tg_queue_mgmt
bash setup.sh
nano .env          # set BOT_TOKEN + ADMIN_IDS
bash run.sh

# Every subsequent time
cd tg_queue_mgmt
bash run.sh
```

Find your WSL machine's IP for network access:
```bash
hostname -I | awk '{print $1}'
```

Then open `http://<that-ip>:8000` from other devices on the same network.

---

## Makefile Shortcuts

```bash
make setup    # same as bash setup.sh
make run      # same as bash run.sh
make install  # re-install/update deps inside venv
make clean    # remove venv and __pycache__
make freeze   # save installed packages back to requirements.txt
```

---

## Architecture

```
┌─────────────────────┐     long-poll      ┌─────────────┐
│  Admin / Customer   │ ◄─────────────────► │  Telegram   │
│  Telegram clients   │                     │  Servers    │
└─────────────────────┘                     └──────┬──────┘
                                                   │ updates
                                            ┌──────▼──────┐
                                            │  bot/main.py │  (asyncio.gather)
                                            │  ┌─────────┐ │
                                            │  │ PTB App │ │  admin.py / customer.py
                                            │  └────┬────┘ │
                                            │       │ DB    │
                                            │  ┌────▼────┐ │
                                            │  │ SQLite  │ │  db/database.py
                                            │  └────┬────┘ │
                                            │       │ broadcast_update()
                                            │  ┌────▼────┐ │
                                            │  │ FastAPI │ │  web/app.py  SSE /events
                                            │  └────┬────┘ │
                                            └───────┼───────┘
                                                    │ HTTP / SSE
                               ┌────────────────────┼─────────────────────┐
                               │                    │                     │
                    ┌──────────▼──────────┐  ┌──────▼──────┐  ┌──────────▼──────────┐
                    │  Browser (index.html)│  │ take.html / │  │  staff_login.html / │
                    │  TTS + Beep + Live  │  │  track.html │  │  staff_dashboard    │
                    │  display (TV view)  │  │  (Customer) │  │  (Staff web UI)     │
                    └─────────────────────┘  └─────────────┘  └─────────────────────┘
```

> **Token numbering** resets to 1 each day per counter. Tokens created on the same calendar day share a sequential numbering sequence.

---

## Screenshots

> _Add screenshots here once deployed._

| Display Page | Admin Bot | Take Token |
|---|---|---|
| _(screenshot)_ | _(screenshot)_ | _(screenshot)_ |

---

## License

MIT
