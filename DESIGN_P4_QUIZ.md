# 🎮 P4 Design — Duolingo-style Quiz (Lesson Path + Mixed Types)

**State:** 📐 Designed, not implemented. Waiting for the go call (checkpoint = P1 done).
**Depends on:** P2 (Kana content in DB) · **Feeds:** P8 (self-learning drill) · **Reuses:** `app/static/js/tts.js`, the chat tile-keyboard pattern, the SurpriseReview MCQ pattern.

---

## 1. What P4 delivers
A Duolingo-style **lesson path** of short **mixed-type quizzes** over the kana the student is learning, with hearts, XP, instant feedback, an end-of-lesson review of missed items, and per-kana mastery tracking. Fully **decoupled** from chats and Dojo (requirement 7).

**Explicitly out of scope** (and why):
- 🚫 **Speech recognition / "speak" exercises** — needs an ASR service; not free-tier friendly. We do TTS *output* only.
- 🚫 **Global leagues with 30 strangers** — replaced by a **per-class leaderboard** (fits the teacher/class model, requirement 3).
- 🚫 **Gem economy / shop** — no virtual currency needed for a classroom tool.
- 🚫 **Stroke tracing in the quiz** — that lives in Dojo (P5/P7).
- ⏸️ **Full HLR model fitting** — we ship an **HLR-lite** scheduler now; the trained model is P8.

---

## 2. Duolingo mechanics → our decisions

| Mechanic | Duolingo | Our call | Why |
|---|---|---|---|
| Learning path | Units → lessons on a winding path | ✅ Adopt: **units = gojūon rows**, vertical list | Simple to render server-side; maps to how kana is taught |
| Lesson length | 5–20 min | ✅ ~**10 questions** per lesson | Short, classroom-friendly |
| Hearts/lives | 5, lose on wrong, refill over time | ⚙️ Adopt but **configurable per class** (default on) | Teachers may disable to reduce frustration for beginners |
| XP | Per correct + bonuses | ✅ Adopt | Cheap motivation |
| Instant feedback + **missed-item review** | Shows correct answer; recaps misses at end | ✅ **Adopt (high value)** | Strong pedagogy, easy to build |
| Streak | Daily, with freezes | ⏸️ **Defer / optional-lite** | Adds state; not core to learning |
| Leagues | Weekly, ~30 users, promote/demote | 🔁 **Per-class leaderboard** | Matches classes; no global matchmaking |
| Legendary / mastery | Hard review level to "max" a unit | ✅ Adopt as **unit checkpoint** (mixed + lookalikes) | Natural mastery gate |
| Quests/achievements | Time-limited goals | ⏸️ Later | Nice-to-have |
| Spaced repetition (HLR) | `p = 2^(−Δ/h)` schedules review | ✅ **HLR-lite now**, full model in P8 | The bridge to your self-learning drill |

---

## 3. Question types (all generatable from existing data)

Every type is **procedurally generated** from the `Kana` table — no hand-authoring thousands of items. Source data per kana: `char`, `romaji`, `exampleWord{kana,romaji,meaning,emoji}`, `mnemonic`, `similarConfusions`, plus the `LOOKALIKE_PAIRS` map (all in `seed/content.json`).

| # | Type | Interaction | Data used | Reuse |
|---|---|---|---|---|
| 1 | **Kana → romaji** (recognition) | See あ, pick "a" from 4 options | romaji + confusions as distractors | SurpriseReview MCQ |
| 2 | **Romaji → kana** (recall) | See "a", pick あ | char + confusions | MCQ |
| 3 | **Listen → pick** | TTS says あ/あさ, pick kana or romaji | `KanaAudio.speak()` | tts.js |
| 4 | **Build word from tiles** | Tap kana tiles to assemble あお (pool has distractors) | exampleWord + lookalikes | chat tile-keyboard |
| 5 | **Match pairs (timed)** | Match kana ↔ romaji grid, beat the clock | row kana set | new small widget |
| 6 | **Lookalike discrimination** | "Which is し?" among し/つ/く | `LOOKALIKE_PAIRS` | MCQ |
| 7 | **Word → meaning** (vocab) | See あさ (asa), pick "Pagi hari" | exampleWord | MCQ |

Distractors are always drawn from the kana's `similarConfusions` / `LOOKALIKE_PAIRS` so wrong options are pedagogically meaningful (the app already does this in chat).

---

## 4. Lesson path structure
- **Tracks:** Hiragana and Katakana (toggle), each with units = rows: vowels, ka, sa, ta, na, ha, ma, ya, ra, wa, n (11 units — matches `HIRAGANA_ORDERED_ROWS`).
- **Unit** = a row (e.g. "Baris Ka"). Contains:
  - **Learn lessons** — introduce 3–5 kana of the row (types 1–4, heavy on new kana).
  - **Unit checkpoint ("Legendary")** — mixed types + lookalike traps across the whole row; unlocks when the learn lessons are done.
- **Mastery gate:** a kana counts as "learned" after ≥ N correct across ≥ 2 different types (N configurable, e.g. 3). Checkpoint requires all unit kana learned.
- **Practice lesson (spaced):** a special always-available lesson that pulls *due* kana from across learned units (HLR-lite) — this is the P8 hook.

---

## 5. Session mechanics (the runner)
- **Hearts:** default 5; −1 per wrong; 0 → lesson failed, offer retry (progress resets). Configurable off per class.
- **Progress bar:** answered / total.
- **XP:** +1 per correct (tune later), + lesson-complete bonus, + perfect-run bonus.
- **Feedback:** correct → green + `KanaAudio.playCorrect()`; wrong → red + `playWrong()` + **reveal correct answer + a one-line reason** (mnemonic or the lookalike rule, e.g. "し ditarik dari BAWAH ke ATAS; つ dari ATAS ke BAWAH").
- **Missed queue:** wrong items are re-asked at the end of the lesson (Duolingo's recap) until answered once correctly.
- **End screen:** XP earned, accuracy %, missed-items recap, "Lanjut".

---

## 6. Spaced repetition — HLR-lite (bridge to P8)
Duolingo's model: recall probability **`p = 2^(−Δ/h)`**, Δ = time since last practice, **h = half-life** learned per item from features (past correct/incorrect counts, item/tag difficulty). Review is scheduled when the learner is "on the verge of forgetting."

**Our HLR-lite (now):**
- Keep per (student, kana): `n_correct`, `n_incorrect`, `last_seen`, and a half-life `h`.
- Simple parametric half-life: `h = 2^(θ0 + θc·n_correct − θw·n_incorrect + θd·difficulty_tag)` with **hand-set weights** to start (no training).
- `p = 2^(−Δ/h)`; a kana is **due** when `p < ~0.85`. Practice lessons and the "review" slots inside learn lessons pull due items first.
- **P8** later: fit θ from the accumulated `AnswerLog` (real HLR / or SM-2/FSRS) — no schema change needed, because we log everything from day one.

---

## 7. Data model (P4 tables; content tables come from P2)
```
Unit(id, track['hiragana'|'katakana'], row, order, title)
Lesson(id, unit_id, order, kind['learn'|'checkpoint'|'practice'], title)
StudentQuizState(id, student_id, xp, streak_days, last_active_date, hearts_enabled?)  # per student
KanaMastery(id, student_id, kana_char, n_correct, n_incorrect, last_seen, half_life, next_due)  # P8 fuel
LessonResult(id, student_id, lesson_id, xp, correct, total, completed_at)
AnswerLog(id, student_id, kana_char, qtype, correct, latency_ms, lesson_id, ts)  # raw events
```
**Reconciliation with PLAN's P2 list:** P2 owns *content* (Kana, Chat, DialogueStep). P4 owns *learning* (above). `AnswerLog` is introduced at the first answer-producing feature (P3 chat or P4 quiz, whichever lands first) so the drill is fed from the start. A stored `Question` model is **optional** — only needed if teachers author custom questions; the core quiz generates from `Kana` (see open decisions).

---

## 8. Architecture (Flask + vanilla JS island)
- Server renders the **path page** and the **lesson shell** (Jinja).
- `GET /quiz/lesson/<id>/questions` → JSON batch: for each question `{type, prompt, kana?, options[]|tiles[], answer, tts_text, explain}`. The generator picks new + due kana and instantiates the type templates.
- A **vanilla JS runner** (`app/static/js/quiz.js`) renders each type, handles input, calls `KanaAudio.speak()`, runs the match timer, applies feedback/hearts/progress, and on finish:
- `POST /quiz/lesson/<id>/result` with per-question outcomes → server writes `AnswerLog`, updates `KanaMastery` (+ `next_due`), `StudentQuizState.xp`, `LessonResult`; returns the summary for the end screen.
- **Answer-checking trust model** (open decision): simplest = send answers to the client and trust it (fine for a low-stakes classroom, works offline-ish); more robust = server-checks each answer (`POST /quiz/answer`) at the cost of a round-trip per question. Recommend client-side + end POST, with answers lightly obfuscated in the payload.

---

## 9. Build breakdown (for when we implement)
1. **P4.1** Models + migration (Unit, Lesson, StudentQuizState, KanaMastery, LessonResult, AnswerLog).
2. **P4.2** Question generator (type templates, new+due selection, lookalike distractors).
3. **P4.3** Path page (units/lessons, locks, progress, track toggle).
4. **P4.4** Lesson runner (`quiz.js` + the 7 type renderers + feedback + hearts + progress + TTS).
5. **P4.5** Result recording + end screen (XP, accuracy, missed recap).
6. **P4.6** Per-class leaderboard.
7. **P4.7** HLR-lite "Practice" lesson (due kana) — the P8 on-ramp.

---

## 10. Open decisions for Salim (decide at implementation time)
1. **Hearts** on by default, or teacher-configurable per class, or off for beginners?
2. **Answer checking:** client-side (simple, cheatable) vs server-checked per question (robust, chattier)?
3. **Custom questions:** do teachers author stored `Question`s, or is purely-generated enough for v1?
4. **Leaderboard scope:** per-class only (recommended) vs school-wide?
5. **Streaks:** ship now or defer?
6. **Romanization helper:** always visible, toggleable, or hidden as difficulty rises?
7. **Mastery threshold N** (correct answers to mark a kana learned) — default 3?
