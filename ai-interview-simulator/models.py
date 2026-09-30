from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    resumes = db.relationship("Resume", backref="user", lazy=True, cascade="all, delete-orphan")
    interviews = db.relationship("Interview", backref="user", lazy=True, cascade="all, delete-orphan")
    weak_topics = db.relationship("WeakTopic", backref="user", lazy=True, cascade="all, delete-orphan")


class Resume(db.Model):
    __tablename__ = "resumes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    extracted_text = db.Column(db.Text, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    interviews = db.relationship("Interview", backref="resume", lazy=True)


class Interview(db.Model):
    __tablename__ = "interviews"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    company = db.Column(db.String(120), nullable=False)
    branch = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), nullable=False)
    difficulty = db.Column(db.String(40), nullable=False)
    mode = db.Column(db.String(40), nullable=False)
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=True)
    score = db.Column(db.Float, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    feedback_json = db.Column(db.Text, nullable=True)

    questions = db.relationship(
        "Question", backref="interview", lazy=True, cascade="all, delete-orphan"
    )


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    interview_id = db.Column(db.Integer, db.ForeignKey("interviews.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(120), nullable=False)
    difficulty = db.Column(db.String(40), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    evaluation = db.Column(db.Text, nullable=True)
    score = db.Column(db.Integer, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)


class WeakTopic(db.Model):
    __tablename__ = "weak_topics"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    weakness_score = db.Column(db.Float, default=50, nullable=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
