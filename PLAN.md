# 🌸 Kana Chat — Flask Rebuild Plan

**Status:** ✅ **P0–P6 done & verified** — auth, roles, classes, content models + seed + editor, chat simulator (no gating), Duolingo quiz path, Dojo tracing, teacher/admin dashboards; migrations applied (`dev.sqlite3`); smoke P1–P6 all pass. **Live deploy to UB BITS Plesk pending your credentials/eligibility confirmation.**
**Build mode:** 🤖 agy (Antigravity) is **credit-blocked (429)** — building directly until credits are topped up.
**Owner:** Salim (solo) • **Budget:** free/low-cost
**Host target:** 🎯 **UB BITS Web Hosting (Plesk)** — primary · **PythonAnywhere free** — fallback
**Rule:** the old React app in `../remix-kana-chat---belajar-hiragana-&-katakana/` is **reference + seed source only**. Nothing there gets deleted or mutated (except one added export script).

---

## 🔒 Locked decisions

| Area | Choice | Why |
|---|---|---|
| Host | **UB BITS Plesk** (primary) | Free campus hosting; **Plesk supports Python** (+php/go/node); always-on, `<nama>.ub.ac.id`, SSL, daily backups, Git deploy, 2 GB SSD. PythonAnywhere = fallback. |
| Backend | **Flask 3** (WSGI) | Runs on Plesk's Python app; your pick. |
| Frontend | **Jinja templates + vanilla JS** | No Node build step; one language. |
| Styling | **Tailwind via CDN** + Google Fonts (`Plus Jakarta Sans`, `M PLUS Rounded 1c`) | Keeps the rose/pink look, zero build. |
| DB | **SQLite (dev)** → **MySQL (Plesk prod)** via SQLAlchemy | SQLite = no local setup; MySQL on host for a whole class writing at once. *(Confirm Plesk MySQL is provisioned.)* |
| Migrations | **Flask-Migrate (Alembic)** | Schema changes without data loss. |
| Auth | **Flask-Login** + Werkzeug hashing + session cookies | "Simple auth, low security need." |
| Roles | `student` / `teacher` / `admin` | Your spec. |
| TTS/audio | **Web Speech API** (browser) | Free, client-side. |
| Env | **conda `kanachat` (Python 3.10)** | Your call: 3.10 = robust. |
| Stroke verify (LATER) | **hanzi-writer** + KanjiVG | Deferred to P7. |

---

## 🌐 Hosting: UB BITS Web Hosting (Plesk)

**Confirmed from the service page:**
- 🧩 **Control panel: Plesk** — supports **PHP, Python, Golang, Node.js** → **Flask runs here.** ✅
- 🌍 Domain: **`<nama>.ub.ac.id`** subdomain (e.g. `fakultas.ub.ac.id`).
- 💾 **2 GB** disk/domain, optimized SSD • 🔒 SSL included • 🗓️ **daily backup, 14-day retention, 1-click restore**.
- 🔀 **Git deploy** (push repo → files land in the hosting dir).
- ⏳ **1-year** active period; re-activate yearly via request letter + form.
- 👥 **Eligibility: official campus units** (fakultas/jurusan/lembaga/unit kerja resmi). Register via **Helpdesk DTI** form + approval.

**❓ Open items to confirm (don't block P1–P5; needed by P6):**
1. **Eligibility path** — it's for official UB units on a `ub.ac.id` domain; notes have you at **UM**, so what's your route? (None → fallback PythonAnywhere.)
2. **MySQL** — page didn't mention DB; confirm you can create MySQL/MariaDB in Plesk + get credentials.
3. **Python app** — confirm Plesk's Python app type is enabled, offers **3.10**, pip-installs from `requirements.txt`; WSGI startup script = `wsgi.py` (exposes `app` + `application`).
4. **Outbound HTTPS** — confirm server may call external APIs (only matters for P9 AI).

---

## 🎯 Your requirements → where each lands

| # | Requirement | Phase |
|---|---|---|
| 1 | 💬 DB-stored chats; teacher/maintainer can edit them | **P2** (models + CRUD editor) |
| 2 | 🔐 student/teacher/admin accounts; username+password register on homepage; simple auth | **P1** |
| 3 | 🏫 student joins class; teacher manages class; admin manages all | **P1** (join flow) + **P6** (dashboards) |
| 4 | 🎮 adopt Duolingo quiz (lesson path + mixed types) | **P4** |
| 5 | 🗑️ remove Buku Tulisanku + Sticker system | **Never ported** (dropped by design) |
| 6 | 🎭 different chat = different context (classmate → class topics) | **P2** (`theme`/`context` field) + **P3** |
| 7 | 🔓 Dojo Menulis no longer required to unlock other chats | **P3/P5** (fully decoupled, no gating) |
| 8 | ✍️ (LATER) Dojo stroke-order verify via KanjiVG + Hanzi Writer | **P7** |

---

## 🗺️ Phase map (each has a binary "done?" test)

- **P0 — Scaffold.** ✅ **DONE.** App factory, config (SQLite dev/MySQL prod), `wsgi.py` + `run.py`, blueprints (main/auth/admin), Tailwind base template, home shell, `/healthz`. Verified 200s.
- **P1 — Auth + Roles + Classes.** ✅ **DONE.** Register/login/logout, `roles_required` guard, teacher creates class → join code → student joins, admin manage-all (users/roles + classes). Verified 19/19 via `scripts/verify_p1.py`.
- **P2 — Content model + seed + editor.** Kana/Chat/DialogueStep/Lesson/Question/**AnswerLog** tables, seeded from the React data, plus teacher/admin CRUD. ✅ *done when 92 kana + 4 chats load from DB and a teacher can edit a chat message in-browser.*
- **P3 — Chat simulator.** Contact list, chat view, kana keyboard, hearts/stars, handwriting canvas, per-context dialogue, no gating. ✅ *done when a student completes a chat that respects its theme.*
- **P4 — Duolingo quiz.** Lesson path, hearts, progress bar, 6 question types, per-student progress saved. ✅ *done when a student finishes a mixed-type lesson with scoring.* → **design in `DESIGN_P4_QUIZ.md`** (7 generatable types, HLR-lite review, per-class leaderboard; 7 open decisions listed there).
- **P5 — Dojo Menulis (decoupled).** Tracing canvas + stroke animation + similarity scoring, reachable anytime. ✅ *done when tracing works standalone with no unlock requirement.*
- **P6 — Dashboards + cleanup + deploy.** Teacher/admin dashboards; deploy to **UB BITS Plesk**. ✅ *done when live at `<nama>.ub.ac.id`.*
- **P7 — (LATER) Stroke-order verification.** hanzi-writer quiz fed by KanjiVG. ✅ *done when Dojo checks stroke order/position, not just shape.*
- **P8 — (FUTURE) Self-learning drill.** Adaptive/spaced-repetition (SM-2/FSRS) + error-weighted selection from the bank, driven by `AnswerLog`. Pure Python, free-tier friendly. ✅ *done when weak kana auto-resurface more often.*
- **P9 — (FUTURE) AI authoring assist.** Optional LLM layer for teachers to draft contextual chats/quizzes (teacher-side/offline). ✅ *done when a teacher can auto-draft a themed chat and edit before publishing.*

> ⚠️ **Scope flag:** Flask (vs Django) means **P2's editing panel is hand-built** — the biggest chunk Django Admin would've given free.
> ⚠️ **Content flag:** the seed only has **4 chat levels** (vowels, ka-, sa-, katakana a-row). More rows = authoring via the P2 editor later, not code now.
> 🧠 **Drill-ready from P2:** every answer gets logged (`AnswerLog`: student, question, correct, ms) from the start — the *only* thing P8 needs, so adaptivity is a drop-in later.

---

## 🤖 AI & self-learning drill (deferred — direction agreed)

Two different things, don't conflate:
- **Adaptive drill (P8) = the real "self-learning", and it's free.** An algorithm (SM-2/FSRS spaced repetition + error-weighted selection) picks what to drill from the bank you already have. No LLM, no GPU. Exactly how Duolingo/Anki work.
- **Generative AI (P9) = optional, later, two catches:**
  1. 🚧 **Outbound calls** — UB BITS Plesk has no published whitelist (confirm), so server-side LLM calls should work; the PythonAnywhere *fallback* does have a whitelist. If ever blocked: teacher-side/offline generation, or client-side/proxied calls.
  2. 🔑 **Key hygiene** — your Alibaba Token Plan key is coding-tools-only (ToS risk); don't wire it into a student app. Use a proper key (OpenRouter/NVIDIA/Google) if/when we add this.

**Verdict:** the win is the *algorithmic* drill, not heavy ML. Build the answer-log now (P2); bolt on P8/P9 later without rework.

---

## 🌳 Decision tree

### ✅ Phase 0 — DONE
Files: `config.py`, `run.py`, `wsgi.py`, `requirements.txt`, `.env.example`, `.gitignore`, `app/{__init__,extensions,models}.py`, `app/{main,auth,admin}/`, `app/templates/{base,main/home,auth/placeholder}.html`, `app/static/css/app.css`.
**Run locally:**
```bash
cd /d/!!STUDYKANA/kana-chat-flask
PYTHONNOUSERSITE=1 /c/Users/Salim/.conda/envs/kanachat/python.exe run.py
# → http://127.0.0.1:5000
```
(Or Anaconda Prompt → `conda activate kanachat` → `python run.py`.)

### ✅ Phase 1 — Auth + Roles + Classes (DONE)
- **1.1** Models: `User` (username, pw hash, role), `Class` (name, teacher_id, join_code), `Enrollment`. Real `user_loader`.
- **1.2** `flask db init` + first migration (creates `dev.sqlite3`).
- **1.3** Register/login/logout routes + templates (replace P0 stubs).
- **1.4** `@roles_required(...)` guard; teacher creates class + roster; student joins by code; admin manage-all.
- ✅ *done when a student registers, joins by code, teacher sees roster.*

### ▶ Phase 2 — Content model + seed + editor (NEXT)
- Export React data → JSON via a **one-time `tsx` script** (reuses the React app's existing `tsx` dep) → `seed/kana.json`, `seed/dialogues.json`.
- Models: `Kana`, `Chat`, `DialogueStep`, `Lesson`, `Question`, `StudentProgress`, `AnswerLog`.
- `seed/load_seed.py` populates DB. Teacher/admin CRUD forms.

### Phases 3–9
Goal-level above; each gets its own decision-tree section when we reach it.

---

## 📌 Next action
**Say "go P1"** and I'll build auth + roles + classes (models, migration, register/login, join-code flow). The 4 host confirmations can happen in parallel — they only gate P6.
