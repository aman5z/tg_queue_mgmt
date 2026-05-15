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
│       ├── index.html     # TV display page
│       ├── style.css      # Dark-theme styles
│       ├── take.html      # Customer token-take form
│       └── track.html     # Customer token-tracking page
├── db/
│   └── database.py        # DB init + all CRUD helpers
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
| `ADMIN_IDS` | recommended | Comma-separated Telegram user IDs with admin access |
| `BASE_URL` | optional | Public URL of this server (default `http://localhost:8000`) |
| `PORT` | optional | Web server port (default `8000`) |

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
                                                    │ SSE stream
                                     ┌──────────────▼──────────────┐
                                     │  Browser (index.html)        │
                                     │  TTS + Beep + Live display   │
                                     └─────────────────────────────┘
```

---

## Screenshots

> _Add screenshots here once deployed._

| Display Page | Admin Bot | Take Token |
|---|---|---|
| _(screenshot)_ | _(screenshot)_ | _(screenshot)_ |

---

## License

MIT
