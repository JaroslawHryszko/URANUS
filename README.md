# URANUS Research Project v3.0 ("Neptune v3")

**URANUS** (Ultra-light Risk ANalysis Using Stepwise Comparison) is an experimental research platform for studying risk assessment methodologies in IT projects. Developed by the Department of Software Engineering at Jagiellonian University, Krakow, Poland.

Version 3.0 is a complete rewrite of the platform, introducing multi-method support, per-session isolation, full interaction tracking, configurable experiments, and an iframe-embeddable interface.

---

## Table of Contents

- [Overview](#overview)
- [Key Changes from v2.0](#key-changes-from-v20)
- [Architecture](#architecture)
- [Risk Assessment Methods](#risk-assessment-methods)
- [Database Schema](#database-schema)
- [Admin Panel](#admin-panel)
- [Participant Flow](#participant-flow)
- [Interaction Tracking](#interaction-tracking)
- [Iframe Embedding](#iframe-embedding)
- [Installation](#installation)
- [Configuration](#configuration)
- [Data Migration from v2.0](#data-migration-from-v20)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [License](#license)
- [Contributors](#contributors)

---

## Overview

The platform enables researchers to design and conduct experiments where participants assess software project risks using multiple configurable methods. The core research question is whether different risk assessment methodologies (pairwise comparison, FMEA matrices, direct ranking, budget allocation, categorization) produce different risk priority rankings — and if so, how and why.

Each experiment is fully self-contained: its own set of risks, assessment methods (with per-method configuration), welcome/instruction texts, demographic fields, and custom CSS. Experiments can be cloned as templates, activated/deactivated, and their results exported in CSV or JSON.

### Core Capabilities

- **5 assessment methods** (A–E), each configurable per experiment
- **Per-session Uranus state** — no global shared state between participants
- **Full interaction tracking** — every click, scroll, focus, hesitation event recorded
- **Configurable experiments** — risks, methods, demographics, texts, CSS — all per-experiment
- **3 method assignment modes** — fixed order, random selection, participant choice
- **Iframe support** — CSP frame-ancestors, SameSite=None cookies, responsive layout
- **Admin panel** — Bootstrap 5 dashboard with CRUD, results, logs, export
- **Data migration** — automatic migration of v2.0 data to the new schema

---

## Key Changes from v2.0

| Aspect | v2.0 | v3.0 |
|---|---|---|
| Uranus state | Global singleton (`global u`) | Per-MethodSession, serialized to DB |
| Methods | 2 (classic + novelty) hardcoded | 5 methods, pluggable registry |
| Risks | Loaded from `config.json` once | Per-experiment in database |
| Sessions | Global `user_name` variable | Proper Flask sessions with DB-backed Session/Participant |
| Configuration | Single `config.json` | Per-experiment DB fields (texts, demographics, CSS, method config) |
| Tracking | Minimal `interaction_log` table | Full client-side tracker.js with 15+ event types |
| Admin panel | View tables + edit config.json | Full CRUD, clone/templates, results view, CSV/JSON export |
| Templates | Custom CSS, no framework | Bootstrap 5 (CDN), responsive, iframe-friendly |
| Dead code | `PrioritizedRisks`, `ClassicRisks`, unused templates | Removed |
| Iframe | Not supported | CSP frame-ancestors + SameSite=None cookies |
| Entry point | `backend.py` | `run.py` with app factory pattern |

---

## Architecture

```
Flask App Factory (app/__init__.py)
├── Blueprints
│   ├── experiment_bp  (/)                — participant-facing flow
│   ├── admin_bp       (/admin)           — admin panel
│   └── api_bp         (/api)             — AJAX endpoints (tracking, metadata)
├── Methods Registry   (app/methods/)     — pluggable assessment method handlers
├── Models             (app/models.py)    — SQLAlchemy ORM (SQLite)
└── Static/Templates   (app/static/, app/templates/)
```

The application uses:
- **Backend**: Flask 3.x + Flask-SQLAlchemy + SQLite
- **Frontend**: Bootstrap 5 (CDN) + SortableJS (CDN) + vanilla JavaScript
- **Auth**: bcrypt password hashing + Flask session
- **Server**: Waitress (production) / Flask dev server (development)
- **Reverse proxy**: Apache2 with SSL (on the `www-lb` container)

---

## Risk Assessment Methods

### A: Pairwise Comparison (Uranus)

The professor's novel algorithm. Participants compare pairs of risks on configurable parameters (default: impact, probability) using binary search insertion sort. The algorithm determines the minimum number of comparisons needed.

- **State**: Serialized to `MethodSession.uranus_state` (JSON) after each comparison
- **Progress**: Calculated from `Uranus.progress()`, shown as a progress bar
- **Result**: Final prioritized ranking via `Uranus.prioritized_list()`
- **Config**: `{"parameters": ["impact", "probability"]}`

The original `uranus.py` is used unmodified. Each participant gets their own `Uranus` instance, created fresh and restored from serialized state on each request.

### B: Matrix / FMEA

Traditional risk matrix. Participants rate each risk on configurable criteria (default: probability 1–5, impact 1–5). Priority is computed as the product or weighted sum.

- **Config**: `{"criteria": [{"name": "probability", "display_name": "Probability", "scale_min": 1, "scale_max": 5, "labels": {"1": "Very Low", ...}}], "aggregation": "product", "weights": {}}`
- **Result**: `{"criteria_values": {"probability": 3, "impact": 4}, "priority": 12}`

### C: Direct Ranking (Drag & Drop)

Participants drag and drop risks into a ranked list from highest to lowest priority. Uses SortableJS for the drag interaction.

- **Config**: `{"mode": "overall", "parameters": []}` — set `mode` to `"per_parameter"` and provide `parameters` list for separate rankings per parameter
- **Result**: `{"rank": 3, "parameter": "overall"}`

### D: Budget Allocation

Participants distribute a fixed number of points (default: 100) among risks. More points = higher priority. Interactive sliders with live remaining-points counter.

- **Config**: `{"total_points": 100, "mode": "overall", "parameters": []}`
- **Validation**: Sum must equal `total_points`, no negative values
- **Result**: `{"points": 15, "parameter": "overall"}`

### E: Categorization (Bucketing)

Participants assign each risk to a category from a configurable list (default: Critical / High / Medium / Low / Negligible).

- **Config**: `{"categories": ["Critical", "High", "Medium", "Low", "Negligible"], "mode": "overall", "parameters": []}`
- **Result**: `{"category": "High", "parameter": "overall"}`

### Adding Custom Methods

Implement a subclass of `BaseMethod` (in `app/methods/base.py`) with 5 methods:
1. `default_config()` — default JSON config
2. `get_template()` — Jinja2 template path
3. `process_response(form_data, method_session, risks)` — handle POST
4. `get_context(method_session, risks)` — template variables for GET
5. `get_results_summary(method_session, risks)` — admin results view

Register in `app/methods/__init__.py` → `METHOD_REGISTRY`.

---

## Database Schema

All models are defined in `app/models.py`. The database is SQLite (file: `instance/data.db`).

### Experiment

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| name | String(255) | Experiment name |
| description | Text | Short description |
| welcome_text | Text | HTML displayed on welcome page |
| instructions | Text | HTML displayed on instructions page |
| is_template | Boolean | Whether this is a clonable template |
| cloned_from_id | FK → Experiment | Source experiment if cloned |
| method_assignment_mode | String | `fixed` / `random` / `participant_choice` |
| method_order | JSON Text | Ordered list of Method IDs (for fixed mode) |
| methods_per_participant | Integer | How many methods to select in random mode (0 = all) |
| demographics_enabled | Boolean | Show demographics form |
| demographics_fields | JSON Text | Field definitions for demographics form |
| custom_css | Text | Per-experiment CSS injected into `<style>` |
| is_active | Boolean | Whether participants can access this experiment |
| created_at, updated_at | DateTime | Timestamps |

### Risk

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| experiment_id | FK → Experiment | |
| name | String(500) | Risk name/description |
| description | Text | Optional longer description |
| order | Integer | Display order |

### Method

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| experiment_id | FK → Experiment | |
| method_type | String | `uranus` / `matrix` / `ranking` / `budget` / `categorization` |
| display_name | String(255) | Shown to participants |
| instructions | Text | HTML shown before the method starts |
| config | JSON Text | Method-specific configuration (see method docs above) |
| order | Integer | Order in fixed mode |
| is_active | Boolean | |

### Participant

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| experiment_id | FK → Experiment | |
| uuid | String(36) UNIQUE | Participant identifier |
| name | String(255) | Name or nickname |
| email | String(255) | Optional |
| demographics | JSON Text | Collected demographic data |
| created_at | DateTime | |

### Session

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| participant_id | FK → Participant | |
| experiment_id | FK → Experiment | |
| started_at | DateTime | |
| completed_at | DateTime | NULL if abandoned |
| user_agent | Text | Browser user agent |
| screen_width, screen_height | Integer | Screen dimensions |
| language | String | Browser language |
| timezone | String | IANA timezone |
| ip_address | String | |
| referrer | Text | HTTP referrer |
| is_iframe | Boolean | Whether loaded in an iframe |

### MethodSession

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| session_id | FK → Session | |
| method_id | FK → Method | |
| order | Integer | Order within the session |
| started_at, completed_at | DateTime | |
| status | String | `pending` / `in_progress` / `completed` / `abandoned` |
| uranus_state | JSON Text | Serialized Uranus instance state (method A only) |

### AssessmentResult

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| method_session_id | FK → MethodSession | |
| risk_id | FK → Risk | NULL for aggregate results (e.g., Uranus final ranking) |
| result_data | JSON Text | Method-specific result (see method docs above) |

### InteractionEvent

| Column | Type | Description |
|---|---|---|
| id | Integer PK | |
| session_id | FK → Session | |
| method_session_id | FK → MethodSession | NULL for page-level events |
| timestamp | Float | Millisecond precision (`performance.now()`) |
| event_type | String | See [Interaction Tracking](#interaction-tracking) |
| element_id | String | Target element ID |
| element_tag | String | Target element tag name |
| element_class | String | Target element CSS classes |
| page_url | Text | Page path |
| event_data | JSON Text | Event-specific payload |

---

## Admin Panel

Access at `/admin/login`. Password is set via `ADMIN_PASSWORD` in `.env`.

### Dashboard (`/admin/`)
- List of all experiments with status (active/inactive/template)
- Per-experiment statistics: participants, sessions, completed, abandoned
- Quick actions: edit, risks, methods, results, participants, logs, activate/deactivate, clone

### Experiment CRUD (`/admin/experiment/<id>/edit`)
- Name, description, welcome text, instructions (HTML)
- Method assignment mode: fixed / random / participant choice
- Methods per participant (for random mode)
- Demographics toggle + JSON field configuration
- Custom CSS
- Active / template flags
- Delete with cascade confirmation

### Risk Management (`/admin/experiment/<id>/risks`)
- Add individual risks or bulk-add (one per line)
- Edit name/description inline
- Drag & drop reordering (SortableJS)
- Delete with confirmation

### Method Management (`/admin/experiment/<id>/methods`)
- Add methods by type (dropdown of 5 types)
- Custom display name and instructions per method
- Edit JSON config directly (criteria, scales, categories, etc.)
- Activate/deactivate individual methods
- Delete with confirmation

### Results (`/admin/experiment/<id>/results`)
- Per-participant, per-method result summaries
- Method-specific display: rankings for Uranus, tables for matrix, etc.
- Export all results as CSV or JSON

### Interaction Logs (`/admin/experiment/<id>/interactions`)
- Filterable by session and event type
- Paginated table (100 events per page)
- Export as CSV or JSON

### Cloning
- Any experiment can be cloned (risks + methods + config copied, data not copied)
- Clones start as inactive
- Use templates for reusable experiment designs

---

## Participant Flow

```
[Welcome Page]  →  [Start: enter name]  →  [Demographics Form]*
      ↓
[Instructions Page]  →  [Method Choice]*  →  [Run Method]
      ↓
[Method Intro]*  →  [Method Assessment]  →  [Between Methods]*  →  ... →  [Complete]
```

\* Optional steps depending on experiment configuration.

### Method Assignment Modes

1. **Fixed** (`method_assignment_mode = "fixed"`): All active methods in configured order. Every participant gets the same methods.
2. **Random** (`method_assignment_mode = "random"`): `methods_per_participant` methods randomly selected and shuffled from the active pool.
3. **Participant Choice** (`method_assignment_mode = "participant_choice"`): Participant selects which methods to complete via checkboxes.

---

## Interaction Tracking

The frontend tracker (`app/static/js/tracker.js`) captures detailed interaction data and sends it to `/api/track` via buffered AJAX calls.

### Tracked Event Types

| Event | Description |
|---|---|
| `page_load` | Page opened (includes URL and referrer) |
| `page_unload` | Page closed (includes time on page) |
| `click` | Any click (element info + coordinates) |
| `change` | Form input value changed |
| `scroll` | Scroll position (sampled every 500ms) |
| `focus` | Window gained focus |
| `blur` | Window lost focus |
| `visibility_change` | Tab hidden/shown |
| `resize` | Window resized |
| `keypress` | Key pressed (element info only, no key value) |
| `form_submit` | Form submitted |
| `hesitation` | No interaction for >10 seconds on a page |

### Buffering

Events are collected in a JavaScript array and flushed:
- Every 5 seconds (periodic interval)
- On `beforeunload` (page close/navigation) via `navigator.sendBeacon()`
- On `form_submit`

### Session Metadata

On page load, `tracker.js` sends a one-time POST to `/api/session_meta` with:
- Screen dimensions (`screen.width`, `screen.height`)
- Browser language (`navigator.language`)
- Timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`)
- Iframe detection (`window !== window.parent`)

---

## Iframe Embedding

The application can be embedded in an iframe on external sites.

### Headers

Flask sets on every response:
```
Content-Security-Policy: frame-ancestors 'self' uranus.edu.pl *.uranus.edu.pl gottlob.frege.ii.uj.edu.pl *.ii.uj.edu.pl
```

No `X-Frame-Options` header is sent (superseded by CSP).

### Cookies

```
SameSite=None; Secure
```

Required for cross-origin iframe session cookies. The `Secure` flag requires HTTPS (provided by Apache reverse proxy with Let's Encrypt).

### Usage

```html
<iframe src="https://gottlob.frege.ii.uj.edu.pl/experiment/1"
        width="100%" height="800" frameborder="0"></iframe>
```

The layout is responsive and works well within iframe constraints.

---

## Installation

### Prerequisites

- Python 3.8+
- pip

### Steps

```bash
# Clone the repository
git clone https://github.com/JaroslawHryszko/neptune.git
cd neptune

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env: set SECRET_KEY, ADMIN_PASSWORD, DATABASE_URI

# Run
python run.py
```

The application will start on `http://0.0.0.0:5000` by default.

---

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-change-me` | Flask secret key for session signing |
| `ADMIN_PASSWORD` | `admin` | Admin panel password |
| `DATABASE_URI` | `sqlite:///data.db` | SQLAlchemy database URI |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5000` | Bind port |
| `FLASK_ENV` | `production` | `development` enables debug mode |

### Per-Experiment Configuration

Everything else is configured per-experiment via the admin panel:
- Welcome text and instructions (HTML)
- Risk definitions (name, description, order)
- Method selection and configuration (JSON)
- Demographics fields (JSON)
- Method assignment mode
- Custom CSS

---

## Data Migration from v2.0

A migration script (`migrate_data.py`) converts v2.0 data to the v3.0 schema:

```bash
# Ensure instance/data_v2_backup.db exists (or instance/data.db from v2)
python migrate_data.py
```

The script:
1. Creates a legacy experiment "ERP Risk Assessment (legacy)" with all 15 risks from `config.json`
2. Creates two methods: Uranus (pairwise) and Matrix (FMEA) with original configurations
3. Migrates `User` → `Participant` (preserving UUIDs)
4. Migrates `ClassicResults` → `AssessmentResult` (method_type=matrix)
5. Migrates `NoveltyResults` → `AssessmentResult` (method_type=uranus)
6. Creates synthetic `Session` and `MethodSession` records grouped by user and timerange
7. Prints validation counts

---

## Deployment

### Production (current setup)

The application runs on the `confluence` LXD container (`172.18.0.33`) as a systemd service:

```ini
# /etc/systemd/system/uranus.service
[Unit]
Description=URANUS Research Application v3
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/neptune
ExecStart=/root/neptune/venv/bin/python /root/neptune/run.py
EnvironmentFile=/root/neptune/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl restart uranus.service
systemctl status uranus.service
```

### Reverse Proxy

Apache2 on the `www-lb` container reverse-proxies `gottlob.frege.ii.uj.edu.pl` → `172.18.0.33:5000` with SSL via Let's Encrypt.

Waitress serves the WSGI app; `ProxyFix` middleware handles `X-Forwarded-*` headers from Apache.

---

## API Reference

### `POST /api/track`

Receives batched interaction events from `tracker.js`.

**Request body** (JSON):
```json
{
  "events": [
    {
      "timestamp": 12345.67,
      "event_type": "click",
      "page_url": "/experiment/1/method/5",
      "event_data": {"element_id": "choice_1", "element_tag": "button", "x": 450, "y": 320}
    }
  ],
  "method_session_id": 5
}
```

**Response**: `{"status": "ok", "count": 1}`

### `POST /api/session_meta`

Receives session metadata (screen size, language, timezone, iframe flag).

**Request body** (JSON):
```json
{
  "screen_width": 1920,
  "screen_height": 1080,
  "language": "en-US",
  "timezone": "Europe/Warsaw",
  "is_iframe": false
}
```

**Response**: `{"status": "ok"}`

---

## Project Structure

```
/root/neptune/
├── run.py                          # Entry point (Waitress / Flask dev server)
├── uranus.py                       # Professor's algorithm (UNCHANGED from v1)
├── migrate_data.py                 # v2.0 → v3.0 data migration
├── requirements.txt                # Python dependencies
├── config.json                     # Legacy risk definitions (used by migrate_data.py)
├── .env                            # Environment variables (not in git)
├── .env.example                    # Template for .env
├── backend.py                      # Legacy v2.0 entry point (kept for reference)
├── instance/
│   ├── data.db                     # SQLite database (not in git)
│   └── data_v2_backup.db           # Pre-migration backup
├── app/
│   ├── __init__.py                 # Flask app factory + blueprint registration
│   ├── config.py                   # Configuration class (reads .env)
│   ├── models.py                   # All SQLAlchemy models (8 tables)
│   ├── admin/
│   │   ├── __init__.py
│   │   └── routes.py               # Admin blueprint: login, CRUD, results, export
│   ├── experiment/
│   │   ├── __init__.py
│   │   └── routes.py               # Participant blueprint: flow, methods, sessions
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # API blueprint: /track, /session_meta
│   ├── methods/
│   │   ├── __init__.py             # Method registry + factory
│   │   ├── base.py                 # Abstract base class
│   │   ├── uranus_method.py        # A: Pairwise comparison wrapper
│   │   ├── matrix.py               # B: Matrix / FMEA
│   │   ├── ranking.py              # C: Drag & drop ranking
│   │   ├── budget.py               # D: Budget allocation
│   │   └── categorization.py       # E: Categorization
│   ├── static/
│   │   ├── css/style.css           # Custom styles (on top of Bootstrap 5)
│   │   └── js/
│   │       ├── tracker.js          # Full interaction tracker
│   │       ├── ranking.js          # SortableJS integration for method C
│   │       └── budget.js           # Live sum validation for method D
│   └── templates/
│       ├── base.html               # Bootstrap 5 base layout
│       ├── admin/
│       │   ├── login.html
│       │   ├── dashboard.html
│       │   ├── experiment_form.html
│       │   ├── risks.html
│       │   ├── methods.html
│       │   ├── participants.html
│       │   ├── results.html
│       │   └── interaction_logs.html
│       ├── experiment/
│       │   ├── welcome.html
│       │   ├── demographics.html
│       │   ├── instructions.html
│       │   ├── method_intro.html
│       │   ├── method_choice.html
│       │   ├── between_methods.html
│       │   └── complete.html
│       └── methods/
│           ├── uranus.html
│           ├── matrix.html
│           ├── ranking.html
│           ├── budget.html
│           └── categorization.html
```

---

## License

This code is distributed under MIT license.

## Contributors

- Jaroslaw Hryszko: jaroslaw.hryszko@uj.edu.pl
- Adam Roman: adam.roman@uj.edu.pl
