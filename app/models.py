"""SQLAlchemy models.

Populated in phases:
  P1 -> User (auth core), Class, Enrollment (classes later)
  P2 -> Kana, Chat, DialogueStep, Lesson, Question, StudentProgress, AnswerLog
"""

import random
import string
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    taught_classes = db.relationship(
        "Classroom",
        back_populates="teacher",
        foreign_keys="Classroom.teacher_id",
        cascade="all, delete-orphan",
    )
    enrollments = db.relationship(
        "Enrollment",
        back_populates="student",
        foreign_keys="Enrollment.student_id",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def password(self) -> str:
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password: str) -> None:
        self.set_password(password)

    def has_role(self, name: str) -> bool:
        return self.role == name

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class Classroom(db.Model):
    __tablename__ = "classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    join_code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    teacher = db.relationship(
        "User",
        back_populates="taught_classes",
        foreign_keys=[teacher_id],
    )
    enrollments = db.relationship(
        "Enrollment",
        back_populates="classroom",
        cascade="all, delete-orphan",
    )

    def __init__(self, **kwargs):
        if "join_code" not in kwargs or not kwargs["join_code"]:
            kwargs["join_code"] = self.generate_join_code()
        super().__init__(**kwargs)

    @classmethod
    def generate_join_code(cls) -> str:
        chars = string.ascii_uppercase + string.digits
        for _ in range(100):
            code = "".join(random.choices(chars, k=6))
            try:
                if not db.session.query(cls).filter_by(join_code=code).first():
                    return code
            except Exception:
                return code
        raise RuntimeError("Failed to generate a unique join code after 100 attempts.")

    def __repr__(self) -> str:
        return f"<Classroom {self.name} ({self.join_code})>"


class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("student_id", "class_id", name="uq_student_class"),
    )

    student = db.relationship(
        "User",
        back_populates="enrollments",
        foreign_keys=[student_id],
    )
    classroom = db.relationship(
        "Classroom",
        back_populates="enrollments",
        foreign_keys=[class_id],
    )

    def __repr__(self) -> str:
        return f"<Enrollment student_id={self.student_id} class_id={self.class_id}>"


class Kana(db.Model):
    __tablename__ = "kana"

    id = db.Column(db.Integer, primary_key=True)
    char = db.Column(db.String(8), unique=True, nullable=False, index=True)
    romaji = db.Column(db.String(16), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # hiragana | katakana
    row = db.Column(db.String(16), nullable=False, index=True)  # gojuon row id, e.g. "a", "ka"
    mnemonic = db.Column(db.Text)
    example_word = db.Column(db.JSON)  # {kana, romaji, meaning, emoji}
    similar_confusions = db.Column(db.JSON)  # list[str]
    strokes = db.Column(db.JSON)  # SVG stroke data, kept for P5/P7

    def __repr__(self) -> str:
        return f"<Kana {self.char} ({self.romaji})>"


class Character(db.Model):
    """NPC chat partners."""

    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    seed_id = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    katakana_name = db.Column(db.String(80))
    role = db.Column(db.String(120))  # e.g. "Teman Sekelas SMA"
    avatar_emoji = db.Column(db.String(16))
    avatar_bg = db.Column(db.String(120))  # tailwind classes
    theme_color = db.Column(db.String(20))
    personality = db.Column(db.Text)
    greeting_voice_note = db.Column(db.Text)

    chats = db.relationship(
        "Chat",
        back_populates="character",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Character {self.name} ({self.seed_id})>"


class KanaRow(db.Model):
    """Display rows for the kana chart (gojuon)."""

    __tablename__ = "kana_rows"

    id = db.Column(db.Integer, primary_key=True)
    row_id = db.Column(db.String(16), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # hiragana | katakana
    chars = db.Column(db.JSON, nullable=False)  # ordered list[str]

    __table_args__ = (
        db.UniqueConstraint("row_id", "type", name="uq_row_type"),
    )

    def __repr__(self) -> str:
        return f"<KanaRow {self.row_id} ({self.type})>"


class Chat(db.Model):
    __tablename__ = "chats"

    id = db.Column(db.Integer, primary_key=True)
    seed_id = db.Column(db.String(60), unique=True, nullable=False, index=True)
    level_number = db.Column(db.Integer, nullable=False)  # display order
    title = db.Column(db.String(160), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    intro_summary = db.Column(db.Text)
    context_theme = db.Column(db.String(120))  # editable situational-context hint
    kanas_introduced = db.Column(db.JSON)  # list[str]
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    character = db.relationship("Character", back_populates="chats")
    steps = db.relationship(
        "DialogueStep",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="DialogueStep.order",
    )

    def __repr__(self) -> str:
        return f"<Chat {self.title} ({self.seed_id})>"


class DialogueStep(db.Model):
    __tablename__ = "dialogue_steps"

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False)
    seed_id = db.Column(db.String(60), nullable=False)  # unique within a chat
    order = db.Column(db.Integer, nullable=False)
    npc_message = db.Column(db.Text, nullable=False)
    npc_romaji = db.Column(db.Text)
    npc_indonesian = db.Column(db.Text)
    is_voice_note = db.Column(db.Boolean, nullable=False, default=False)
    is_handwriting_challenge = db.Column(db.Boolean, nullable=False, default=False)
    handwriting_target_char = db.Column(db.String(8))
    required_reply_kana = db.Column(db.String(60))
    required_reply_romaji = db.Column(db.String(120))
    required_reply_indonesian = db.Column(db.String(200))
    allowed_alternatives = db.Column(db.JSON)  # list[str] of accepted replies
    available_kana_pool = db.Column(db.JSON)  # list[str] for the on-screen keyboard
    wrong_reaction = db.Column(db.Text)
    wrong_reaction_romaji = db.Column(db.Text)

    chat = db.relationship("Chat", back_populates="steps")

    __table_args__ = (
        db.UniqueConstraint("chat_id", "seed_id", name="uq_chat_step"),
    )

    def __repr__(self) -> str:
        return f"<DialogueStep {self.seed_id} (chat_id={self.chat_id})>"


class AnswerLog(db.Model):
    """Every answer-producing interaction gets logged; powers P8 adaptive drill."""

    __tablename__ = "answer_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=True)
    step_id = db.Column(db.Integer, db.ForeignKey("dialogue_steps.id"), nullable=True)
    question_type = db.Column(db.String(20), nullable=False, default="chat")
    is_correct = db.Column(db.Boolean, nullable=False)
    response_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.Index("ix_answer_logs_student_created", "student_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AnswerLog student={self.student_id} correct={self.is_correct}>"


class StudentChatState(db.Model):
    """Per-student progress through a chat scenario."""

    __tablename__ = "student_chat_states"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    chat_id = db.Column(db.Integer, db.ForeignKey("chats.id"), nullable=False)
    current_step_order = db.Column(db.Integer, nullable=False, default=0)
    stars = db.Column(db.Integer, nullable=False, default=0)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    hearts = db.Column(db.Integer, nullable=False, default=5)
    wrong_count = db.Column(db.Integer, nullable=False, default=0)
    hint_count = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    student = db.relationship("User", backref="chat_states")
    chat = db.relationship("Chat", backref="student_states")

    __table_args__ = (
        db.UniqueConstraint("student_id", "chat_id", name="uq_student_chat"),
    )

    def __repr__(self) -> str:
        return f"<StudentChatState student={self.student_id} chat={self.chat_id} step={self.current_step_order}>"


class Unit(db.Model):
    """A gojūon row within a hiragana/katakana track."""

    __tablename__ = "units"

    id = db.Column(db.Integer, primary_key=True)
    track = db.Column(db.String(10), nullable=False)  # hiragana | katakana
    row = db.Column(db.String(16), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(160), nullable=False)

    __table_args__ = (db.UniqueConstraint("track", "row", name="uq_unit_track_row"),)

    lessons = db.relationship(
        "Lesson",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="Lesson.order",
    )

    def __repr__(self) -> str:
        return f"<Unit {self.track} {self.row}>"


class Lesson(db.Model):
    """One playable lesson inside a unit."""

    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), nullable=False)  # learn | checkpoint | practice
    title = db.Column(db.String(160), nullable=False)
    n_questions = db.Column(db.Integer, nullable=False, default=10)
    requires_prior = db.Column(db.Boolean, nullable=False, default=False)

    unit = db.relationship("Unit", back_populates="lessons")
    results = db.relationship(
        "LessonResult",
        back_populates="lesson",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("unit_id", "kind", name="uq_unit_lesson_kind"),
    )

    def __repr__(self) -> str:
        return f"<Lesson {self.kind} {self.title}>"


class StudentQuizState(db.Model):
    """Per-student aggregate quiz progress."""

    __tablename__ = "student_quiz_states"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    xp = db.Column(db.Integer, nullable=False, default=0)
    hearts_enabled = db.Column(db.Boolean, nullable=False, default=True)

    student = db.relationship("User", backref="quiz_state", uselist=False)

    def __repr__(self) -> str:
        return f"<StudentQuizState student={self.student_id} xp={self.xp}>"


class KanaMastery(db.Model):
    """Per (student, kana) mastery; feeds P8 spaced repetition."""

    __tablename__ = "kana_mastery"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kana_char = db.Column(db.String(8), db.ForeignKey("kana.char"), nullable=False, index=True)
    n_correct = db.Column(db.Integer, nullable=False, default=0)
    n_incorrect = db.Column(db.Integer, nullable=False, default=0)
    last_seen = db.Column(db.DateTime)
    half_life = db.Column(db.Float, nullable=False, default=1.0)  # days
    next_due = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("student_id", "kana_char", name="uq_student_kana"),
    )

    def __repr__(self) -> str:
        return f"<KanaMastery {self.kana_char} c={self.n_correct} i={self.n_incorrect}>"


class LessonResult(db.Model):
    """Record of a student completing a lesson."""

    __tablename__ = "lesson_results"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False, index=True)
    xp = db.Column(db.Integer, nullable=False, default=0)
    correct = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False, default=0)
    completed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    lesson = db.relationship("Lesson", back_populates="results")

    def __repr__(self) -> str:
        return f"<LessonResult student={self.student_id} lesson={self.lesson_id} {self.correct}/{self.total}>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None
