# InteractiveAI — Railway Dispatcher (Local Deployment)

AI-powered railway dispatching prototype built on the InteractiveAI platform.  
This branch: [`FHNWtec-version`](https://github.com/ainetus/InteractiveAI/tree/FHNWtec-version)

---

## Prerequisites

Install the following before proceeding (order does not matter):

| Tool | Version | Link | Notes |
|------|---------|------|-------|
| Docker Desktop | Latest | https://www.docker.com/products/docker-desktop | Restart PC after install. Must remain open while using the app. |
| Python | **3.10 exactly** | https://www.python.org/downloads/release/python-31011/ | ✅ Check **"Add Python to PATH"** during install |
| Node.js | LTS (18+) | https://nodejs.org/ | Any recent LTS version works |

> **Important:** Python 3.10 is required exactly — the Flatland simulation library does not support other versions.

---

## Installation

### 1. Get the code

Clone the repository (requires Git):
```bash
git clone -b FHNWtec-version https://github.com/ainetus/InteractiveAI.git
```

Or download the ZIP directly:  
👉 https://github.com/ainetus/InteractiveAI/tree/FHNWtec-version → **Code → Download ZIP** → extract

---

### 2. Start Docker Desktop

Open Docker Desktop and wait until it shows **"Engine running"** before continuing.  
Docker must remain open the entire time you use the application.

---

### 3. Run the installer (once per machine)

**Windows:** Double-click `install.bat`

**Linux/macOS:**
```bash
chmod +x install.sh start.sh
./install.sh
```

This sets up the Python virtual environment, installs npm packages, and builds the Railway frontend. Takes a few minutes on first run.

> `install.bat` / `install.sh` only needs to run once per machine. It is safe to run again if something goes wrong.

---

### 4. Launch the application

**Windows:** Double-click `start.bat`

**Linux/macOS:**
```bash
./start.sh
```

The startup script will:
1. Start all Docker services (~25 seconds)
2. Configure the database
3. Load the business configuration
4. Start the Flask simulation brain (port 5001)
5. Start the Angular ZWL frontend (port 4200)
6. Open the browser automatically after ~15 seconds

> Run `start.bat` / `start.sh` every time you want to launch the application.

---

## Accessing the Application

The browser should open automatically. If it doesn't, go to:

**http://localhost:3200/cab/Railway**

**Login credentials:**
- Username: `railway_user`
- Password: `test`

> Do **not** log in as `admin` — notification cards will not appear for the admin user.

---

## Usage

The application has three modes, selectable from the left panel:

### Free Mode
Load and run any scenario freely. Useful for exploring and testing.  
Decisions are **not logged**.

### Experiment Mode
Simulates the full user study conditions:
- Login with a participant acronym is required before starting
- All 6 scenarios are played in sequence — 3 in co-learning mode, 3 in recommendation mode (randomly assigned and shuffled each time)
- Reflection questions appear after each scenario
- All decisions, KPIs, and reflection answers are **logged to a JSON file**

### Testprotokoll
Same as Experiment Mode but plays only a single scenario:
- User can freely choose the scenario and mode (co-learning or recommendation)
- Useful for onboarding participants or testing individual scenarios
- Decisions and reflection answers are **logged**

---

## Troubleshooting

**The page shows an old operations dashboard instead of the Railway dispatcher**  
Wait 10 seconds and refresh the page (Ctrl+R). The correct interface will load once the frontend is ready.

**Notification cards don't appear (bell shows "offline")**  
Log out and log back in as `railway_user`. The SSE connection re-establishes on login.

**Windows SmartScreen warns about install.bat or start.bat**  
Click **"More info" → "Run anyway"**. This is expected for unsigned batch files.

**Port conflict — app won't load**  
Ensure ports `3200`, `5001`, and `4200` are not in use by other applications before running `start.bat`.

**Double-clicking start.bat closes immediately without opening the browser**  
Run it from Command Prompt to see the error:
```cmd
cd C:\path\to\InteractiveAI
start.bat
```

**App works but Docker Desktop is closed**  
All services run inside Docker — if Docker Desktop closes, the app stops. Reopen Docker Desktop and run `start.bat` again.

---

## Ports used

| Port | Service |
|------|---------|
| 3200 | InteractiveAI web interface |
| 5001 | Flask Railway simulation brain |
| 4200 | Angular ZWL diagram view |

---

## Stopping the application

Close the Flask and Angular terminal windows, then run:
```bash
docker compose -f config/dev/cab-standalone/docker-compose.yml down
```
Or simply close Docker Desktop to stop all services.
