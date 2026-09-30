import json
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env",
    override=True
)


# ============================================================
# OPTIONAL VIDEO ANALYSIS IMPORTS
# ============================================================

try:
    import cv2
except ImportError:
    cv2 = None


# ============================================================
# FLASK IMPORTS
# ============================================================

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from flask_wtf import CSRFProtect

from werkzeug.exceptions import RequestEntityTooLarge

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from config import Config

from models import (
    db,
    User,
    Resume,
    Interview,
    Question,
    WeakTopic,
)

from services.ai_service import (
    AIService,
    AIServiceError,
)

from services.interview_service import (
    calculate_interview_score,
    build_feedback_payload,
    update_weak_topics,
)

from services.resume_service import (
    ResumeService,
    ResumeServiceError,
)

from services.data import (
    COMPANIES,
    BRANCHES,
    ROLES,
    DIFFICULTIES,
    MODES,
    RESOURCES,
    BOOKS,
    CODING_PLATFORMS,
)


# ============================================================
# CREATE FLASK APP
# ============================================================

app = Flask(__name__)

app.config.from_object(Config)


# ============================================================
# CREATE REQUIRED FOLDERS
# ============================================================

Path(
    app.config["UPLOAD_FOLDER"]
).mkdir(
    parents=True,
    exist_ok=True
)

Path(
    app.config["INSTANCE_PATH"]
).mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# DATABASE
# ============================================================

db.init_app(app)


# ============================================================
# CSRF
# ============================================================

csrf = CSRFProtect(app)


# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager(app)

login_manager.login_view = "login"

login_manager.login_message = (
    "Please log in to continue."
)

login_manager.login_message_category = "warning"


# ============================================================
# SERVICES
# ============================================================

ai = AIService()

resume_service = ResumeService()


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

with app.app_context():

    db.create_all()


# ============================================================
# USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id)
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# GLOBAL TEMPLATE DATA
# ============================================================

@app.context_processor
def inject_globals():

    return {
        "app_name": "AI Interview Simulator",

        "companies": COMPANIES,

        "branches": BRANCHES,

        "roles": ROLES,

        "difficulties": DIFFICULTIES,

        "modes": MODES,
    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "index.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm = request.form.get(
            "confirm_password",
            ""
        )

        errors = []

        # ------------------------------
        # NAME
        # ------------------------------

        if len(name) < 2:

            errors.append(
                "Please enter your full name."
            )

        # ------------------------------
        # EMAIL
        # ------------------------------

        if (
            "@" not in email
            or "." not in email.split("@")[-1]
        ):

            errors.append(
                "Please enter a valid email address."
            )

        # ------------------------------
        # PASSWORD
        # ------------------------------

        if (
            len(password) < 8
            or not any(
                c.isalpha()
                for c in password
            )
            or not any(
                c.isdigit()
                for c in password
            )
        ):

            errors.append(
                "Password must be at least "
                "8 characters and contain "
                "letters and numbers."
            )

        # ------------------------------
        # CONFIRM PASSWORD
        # ------------------------------

        if password != confirm:

            errors.append(
                "Passwords do not match."
            )

        # ------------------------------
        # DUPLICATE EMAIL
        # ------------------------------

        if User.query.filter_by(
            email=email
        ).first():

            errors.append(
                "An account with this email "
                "already exists."
            )

        # ------------------------------
        # SHOW ERRORS
        # ------------------------------

        if errors:

            for error in errors:

                flash(
                    error,
                    "danger"
                )

        else:

            user = User(

                name=name,

                email=email,

                password_hash=
                generate_password_hash(
                    password
                ),
            )

            db.session.add(user)

            db.session.commit()

            login_user(
                user,
                remember=True
            )

            flash(
                "Account created successfully. "
                "Welcome!",
                "success"
            )

            return redirect(
                url_for("dashboard")
            )

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user.is_authenticated:

        return redirect(
            url_for("dashboard")
        )

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if (
            not user
            or not check_password_hash(
                user.password_hash,
                password
            )
        ):

            flash(
                "Invalid email or password.",
                "danger"
            )

        else:

            login_user(
                user,
                remember=True
            )

            next_url = request.args.get(
                "next"
            )

            if (
                not next_url
                or not next_url.startswith("/")
            ):

                next_url = url_for(
                    "dashboard"
                )

            return redirect(
                next_url
            )

    return render_template(
        "login.html"
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "You have been logged out.",
        "info"
    )

    return redirect(
        url_for("index")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    interviews = (
        Interview.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Interview.started_at.desc()
        )
        .all()
    )

    completed = [
        interview
        for interview in interviews
        if interview.completed_at
    ]

    scores = [
        interview.score
        for interview in completed
        if interview.score is not None
    ]

    questions_answered = 0

    for interview in completed:

        questions_answered += (
            Question.query
            .filter_by(
                interview_id=interview.id
            )
            .filter(
                Question.user_answer.isnot(None)
            )
            .count()
        )

    weak = (
        WeakTopic.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            WeakTopic.weakness_score.desc()
        )
        .first()
    )

    strong = (
        WeakTopic.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            WeakTopic.weakness_score.asc()
        )
        .first()
    )

    current_level = (
        interviews[0].difficulty
        if interviews
        else "Beginner"
    )

    average_score = (
        round(
            sum(scores) / len(scores),
            1
        )
        if scores
        else 0
    )

    return render_template(

        "dashboard.html",

        interviews=interviews[:8],

        completed_count=len(
            completed
        ),

        average_score=average_score,

        questions_answered=
        questions_answered,

        weakest=(
            weak.topic
            if weak
            else "Not enough data"
        ),

        strongest=(
            strong.topic
            if (
                strong
                and strong.weakness_score < 35
            )
            else "Building profile"
        ),

        current_level=current_level,
    )


# ============================================================
# COMPANIES
# ============================================================

@app.route("/companies")
@login_required
def companies_page():

    return render_template(
        "companies.html"
    )


# ============================================================
# COMPANY DETAILS
# ============================================================

@app.route("/companies/<slug>")
@login_required
def company_detail(slug):

    company = next(
        (
            company
            for company in COMPANIES
            if company["slug"] == slug
        ),
        None
    )

    if not company:

        flash(
            "Company not found.",
            "danger"
        )

        return redirect(
            url_for("companies_page")
        )

    return render_template(
        "company_detail.html",
        company=company
    )


# ============================================================
# START INTERVIEW
# ============================================================

@app.route(
    "/start-interview",
    methods=["GET", "POST"]
)
@login_required
def start_interview():

    if request.method == "POST":

        company_slug = request.form.get(
            "company",
            ""
        )

        branch = request.form.get(
            "branch",
            ""
        )

        role = request.form.get(
            "role",
            ""
        )

        difficulty = request.form.get(
            "difficulty",
            ""
        )

        mode = request.form.get(
            "mode",
            ""
        )

        company = next(
            (
                c
                for c in COMPANIES
                if c["slug"] == company_slug
            ),
            None
        )

        valid_branches = {
            b["name"]
            for b in BRANCHES
        }

        valid_roles = {
            r["name"]
            for r in ROLES
        }

        valid_difficulties = {
            d["name"]
            for d in DIFFICULTIES
        }

        valid_modes = {
            m["name"]
            for m in MODES
        }

        if (
            not company
            or branch not in valid_branches
            or role not in valid_roles
        ):

            flash(
                "Please choose valid interview settings.",
                "danger"
            )

            return render_template(
                "interview_setup.html"
            )

        if (
            difficulty not in valid_difficulties
            or mode not in valid_modes
        ):

            flash(
                "Please choose a valid difficulty "
                "and interview mode.",
                "danger"
            )

            return render_template(
                "interview_setup.html"
            )

        # --------------------------------
        # RESUME
        # --------------------------------

        resume = None

        upload = request.files.get(
            "resume"
        )

        if upload and upload.filename:

            try:

                resume = (
                    resume_service
                    .save_and_extract(
                        upload,
                        current_user.id
                    )
                )

                db.session.add(
                    resume
                )

                db.session.flush()

            except ResumeServiceError as exc:

                db.session.rollback()

                flash(
                    str(exc),
                    "danger"
                )

                return render_template(
                    "interview_setup.html"
                )

        else:

            resume = (
                Resume.query
                .filter_by(
                    user_id=current_user.id
                )
                .order_by(
                    Resume.uploaded_at.desc()
                )
                .first()
            )

        # --------------------------------
        # CREATE INTERVIEW
        # --------------------------------

        interview = Interview(

            user_id=current_user.id,

            company=company["name"],

            branch=branch,

            role=role,

            difficulty=difficulty,

            mode=mode,

            resume_id=(
                resume.id
                if resume
                else None
            ),

            started_at=datetime.utcnow(),
        )

        db.session.add(
            interview
        )

        db.session.commit()

        # --------------------------------
        # GET WEAK TOPICS
        # --------------------------------

        weak_topics = [

            {
                "topic": weak.topic,

                "subject": weak.subject,

                "score": weak.weakness_score,
            }

            for weak in (
                WeakTopic.query
                .filter_by(
                    user_id=current_user.id
                )
                .order_by(
                    WeakTopic.weakness_score.desc()
                )
                .limit(8)
                .all()
            )
        ]

        # --------------------------------
        # GENERATE FIRST QUESTION
        # --------------------------------

        try:

            question_data = (
                ai.generate_question(

                    company=company,

                    branch=branch,

                    role=role,

                    difficulty=difficulty,

                    resume_text=(
                        resume.extracted_text
                        if resume
                        else ""
                    ),

                    previous_questions=[],

                    weak_topics=weak_topics,

                    progress=0,
                )
            )

        except AIServiceError as exc:

            db.session.delete(
                interview
            )

            db.session.commit()

            flash(
                str(exc),
                "danger"
            )

            return redirect(
                url_for(
                    "start_interview"
                )
            )

        # --------------------------------
        # SAVE FIRST QUESTION
        # --------------------------------

        question = Question(

            interview_id=interview.id,

            question_text=
            question_data["question"],

            category=
            question_data.get(
                "category",
                "Technical"
            ),

            topic=
            question_data.get(
                "topic",
                "General"
            ),

            difficulty=
            question_data.get(
                "difficulty",
                difficulty
            ),
        )

        db.session.add(
            question
        )

        db.session.commit()

        return redirect(
            url_for(
                "take_interview",

                interview_id=
                interview.id,

                question_id=
                question.id,
            )
        )

    return render_template(
        "interview_setup.html"
    )


# ============================================================
# TAKE INTERVIEW
# ============================================================

@app.route(
    "/interview/<int:interview_id>/question/<int:question_id>"
)
@login_required
def take_interview(
    interview_id,
    question_id
):

    interview = db.session.get(
        Interview,
        interview_id
    )

    question = db.session.get(
        Question,
        question_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        flash(
            "Interview not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if (
        not question
        or question.interview_id
        != interview.id
    ):

        flash(
            "Question not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if interview.completed_at:

        return redirect(
            url_for(
                "feedback",
                interview_id=interview.id
            )
        )

    answered = (
        Question.query
        .filter_by(
            interview_id=interview.id
        )
        .filter(
            Question.user_answer.isnot(None)
        )
        .count()
    )

    return render_template(

        "interview.html",

        interview=interview,

        question=question,

        answered=answered,

        max_questions=
        app.config["MAX_QUESTIONS"],
    )


# ============================================================
# SUBMIT ANSWER
# ============================================================

@app.route(
    "/api/interview/<int:interview_id>/answer",
    methods=["POST"]
)
@login_required
def submit_answer(interview_id):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        return jsonify(
            {
                "error":
                "Unauthorized interview."
            }
        ), 403

    if interview.completed_at:

        return jsonify(
            {
                "done": True,

                "redirect": url_for(
                    "feedback",
                    interview_id=
                    interview.id
                ),
            }
        )

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )

    question_id = payload.get(
        "question_id"
    )

    answer = (
        payload.get("answer")
        or ""
    ).strip()

    if not question_id:

        return jsonify(
            {
                "error":
                "Question ID is missing."
            }
        ), 400

    try:

        question_id = int(
            question_id
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify(
            {
                "error":
                "Invalid question ID."
            }
        ), 400

    question = db.session.get(
        Question,
        question_id
    )

    if (
        not question
        or question.interview_id
        != interview.id
    ):

        return jsonify(
            {
                "error":
                "Question not found."
            }
        ), 404

    if not answer:

        return jsonify(
            {
                "error":
                "Please provide an answer "
                "before submitting."
            }
        ), 400

    # ========================================================
    # INTERNET INTERRUPTION PROTECTION
    # ========================================================

    if question.user_answer is not None:

        answered_count = (
            Question.query
            .filter_by(
                interview_id=
                interview.id
            )
            .filter(
                Question.user_answer.isnot(None)
            )
            .count()
        )

        if (
            answered_count
            >= app.config["MAX_QUESTIONS"]
        ):

            complete_interview(
                interview
            )

            return jsonify(
                {
                    "done": True,

                    "already_processed":
                    True,

                    "evaluation": {
                        "score":
                        question.score or 0,

                        "feedback":
                        question.evaluation
                        or "",

                        "classification": (
                            "correct"
                            if question.is_correct
                            else "incorrect"
                        ),
                    },

                    "redirect": url_for(
                        "feedback",
                        interview_id=
                        interview.id
                    ),
                }
            )

        existing_next = (
            Question.query
            .filter_by(
                interview_id=
                interview.id
            )
            .filter(
                Question.user_answer.is_(None)
            )
            .order_by(
                Question.id.asc()
            )
            .first()
        )

        if existing_next:

            return jsonify(
                {
                    "done": False,

                    "already_processed":
                    True,

                    "evaluation": {
                        "score":
                        question.score or 0,

                        "feedback":
                        question.evaluation
                        or "",

                        "classification": (
                            "correct"
                            if question.is_correct
                            else "incorrect"
                        ),
                    },

                    "next_url": url_for(
                        "take_interview",

                        interview_id=
                        interview.id,

                        question_id=
                        existing_next.id,
                    ),
                }
            )

        return jsonify(
            {
                "done": False,

                "already_processed":
                True,

                "evaluation": {
                    "score":
                    question.score or 0,

                    "feedback":
                    question.evaluation
                    or "",

                    "classification": (
                        "correct"
                        if question.is_correct
                        else "incorrect"
                    ),
                },

                "next_url": url_for(
                    "next_question",
                    interview_id=
                    interview.id
                ),
            }
        )

    # ========================================================
    # EVALUATE NEW ANSWER
    # ========================================================

    resume_text = (
        interview.resume.extracted_text
        if interview.resume
        else ""
    )

    try:

        evaluation = (
            ai.evaluate_answer(

                question=
                question.question_text,

                category=
                question.category,

                topic=
                question.topic,

                difficulty=
                question.difficulty,

                answer=answer,

                resume_text=
                resume_text,
            )
        )

    except AIServiceError as exc:

        return jsonify(
            {
                "error":
                str(exc)
            }
        ), 502

    # ========================================================
    # SAVE ANSWER
    # ========================================================

    question.user_answer = answer

    question.evaluation = (
        evaluation.get(
            "feedback",
            ""
        )
    )

    try:

        question.score = max(
            0,
            min(
                100,
                int(
                    evaluation.get(
                        "score",
                        0
                    )
                )
            )
        )

    except (
        TypeError,
        ValueError
    ):

        question.score = 0

    question.is_correct = (
        str(
            evaluation.get(
                "classification",
                "incorrect"
            )
        ).lower()
        == "correct"
    )

    db.session.commit()

    # ========================================================
    # UPDATE WEAK TOPICS
    # ========================================================

    try:

        update_weak_topics(

            user_id=
            current_user.id,

            topic=
            question.topic,

            subject=
            question.category,

            score=
            question.score,

            weak_topics=
            evaluation.get(
                "weak_topics",
                []
            ),
        )

    except Exception:

        db.session.rollback()

    # ========================================================
    # COUNT ANSWERED
    # ========================================================

    answered_count = (
        Question.query
        .filter_by(
            interview_id=
            interview.id
        )
        .filter(
            Question.user_answer.isnot(None)
        )
        .count()
    )

    # ========================================================
    # MAX QUESTIONS
    # ========================================================

    if (
        answered_count
        >= app.config["MAX_QUESTIONS"]
    ):

        complete_interview(
            interview
        )

        return jsonify(
            {
                "done": True,

                "evaluation":
                evaluation,

                "redirect": url_for(
                    "feedback",

                    interview_id=
                    interview.id
                ),
            }
        )

    # ========================================================
    # NORMAL CASE
    # ========================================================

    return jsonify(
        {
            "done": False,

            "evaluation":
            evaluation,

            "next_url": url_for(
                "next_question",

                interview_id=
                interview.id,
            ),
        }
    )


# ============================================================
# NEXT QUESTION
# ============================================================

@app.route(
    "/interview/<int:interview_id>/next",
    methods=["GET", "POST"]
)
@login_required
def next_question(interview_id):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        flash(
            "Interview not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if interview.completed_at:

        return redirect(
            url_for(
                "feedback",
                interview_id=
                interview.id
            )
        )

    questions = (
        Question.query
        .filter_by(
            interview_id=
            interview.id
        )
        .order_by(
            Question.id.asc()
        )
        .all()
    )

    answered = [
        q
        for q in questions
        if q.user_answer is not None
    ]

    if (
        len(answered)
        >= app.config["MAX_QUESTIONS"]
    ):

        complete_interview(
            interview
        )

        return redirect(
            url_for(
                "feedback",
                interview_id=
                interview.id
            )
        )

    # ========================================================
    # REUSE UNANSWERED QUESTION
    # ========================================================

    unanswered = [
        q
        for q in questions
        if q.user_answer is None
    ]

    if unanswered:

        existing_question = (
            unanswered[0]
        )

        return redirect(
            url_for(

                "take_interview",

                interview_id=
                interview.id,

                question_id=
                existing_question.id,
            )
        )

    # ========================================================
    # GENERATE NEW QUESTION
    # ========================================================

    resume_text = (
        interview.resume.extracted_text
        if interview.resume
        else ""
    )

    weak_topics = [

        {
            "topic":
            weak.topic,

            "subject":
            weak.subject,

            "score":
            weak.weakness_score,
        }

        for weak in (
            WeakTopic.query
            .filter_by(
                user_id=
                current_user.id
            )
            .order_by(
                WeakTopic.weakness_score.desc()
            )
            .limit(8)
            .all()
        )
    ]

    company = next(
        (
            c
            for c in COMPANIES
            if c["name"]
            == interview.company
        ),
        None
    )

    if not company:

        company = {

            "name":
            interview.company,

            "description":
            "",

            "skills":
            [],

            "technical_topics":
            [],

            "roles":
            [],
        }

    previous_questions = [

        {
            "question":
            q.question_text,

            "category":
            q.category,

            "topic":
            q.topic,

            "difficulty":
            q.difficulty,

            "score":
            q.score,
        }

        for q in questions
    ]

    try:

        question_data = (
            ai.generate_question(

                company=
                company,

                branch=
                interview.branch,

                role=
                interview.role,

                difficulty=
                interview.difficulty,

                resume_text=
                resume_text,

                previous_questions=
                previous_questions,

                weak_topics=
                weak_topics,

                progress=
                len(answered),
            )
        )

    except AIServiceError as exc:

        flash(
            str(exc),
            "danger"
        )

        return render_template(

            "error.html",

            code=503,

            message=(
                "The AI could not generate "
                "the next question. "
                "Please try again."
            )

        ), 503

    question = Question(

        interview_id=
        interview.id,

        question_text=
        question_data["question"],

        category=
        question_data.get(
            "category",
            "Technical"
        ),

        topic=
        question_data.get(
            "topic",
            "General"
        ),

        difficulty=
        question_data.get(
            "difficulty",
            interview.difficulty
        ),
    )

    db.session.add(
        question
    )

    db.session.commit()

    return redirect(
        url_for(

            "take_interview",

            interview_id=
            interview.id,

            question_id=
            question.id,
        )
    )


# ============================================================
# COMPLETE INTERVIEW
# ============================================================

def complete_interview(interview):

    if interview.completed_at:

        return

    questions = (
        Question.query
        .filter_by(
            interview_id=
            interview.id
        )
        .all()
    )

    answered = [
        q
        for q in questions
        if q.user_answer is not None
    ]

    interview.score = (
        calculate_interview_score(
            answered
        )
    )

    interview.completed_at = (
        datetime.utcnow()
    )

    db.session.commit()


# ============================================================
# FEEDBACK
# ============================================================

@app.route(
    "/interview/<int:interview_id>/feedback"
)
@login_required
def feedback(interview_id):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        flash(
            "Interview not found.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    if not interview.completed_at:

        complete_interview(
            interview
        )

    questions = (
        Question.query
        .filter_by(
            interview_id=
            interview.id
        )
        .order_by(
            Question.id.asc()
        )
        .all()
    )

    payload = build_feedback_payload(
        interview,
        questions
    )

    if not interview.feedback_json:

        try:

            generated = (
                ai.generate_feedback(
                    payload
                )
            )

            interview.feedback_json = (
                json_dumps_safe(
                    generated
                )
            )

            db.session.commit()

            feedback_data = generated

        except AIServiceError:

            feedback_data = (
                payload[
                    "fallback_feedback"
                ]
            )

    else:

        feedback_data = (
            json_loads_safe(
                interview.feedback_json,

                payload[
                    "fallback_feedback"
                ]
            )
        )

    # ========================================================
    # LOAD VOICE / VIDEO ANALYSIS
    # ========================================================

    analysis = load_interview_analysis(
        interview.id
    )

    return render_template(

        "feedback.html",

        interview=interview,

        questions=questions,

        feedback=feedback_data,

        analysis=analysis,
    )


# ============================================================
# HISTORY
# ============================================================

@app.route("/history")
@login_required
def history():

    interviews = (
        Interview.query
        .filter_by(
            user_id=
            current_user.id
        )
        .order_by(
            Interview.started_at.desc()
        )
        .all()
    )

    return render_template(

        "history.html",

        interviews=interviews
    )


# ============================================================
# PROGRESS
# ============================================================

@app.route("/progress")
@login_required
def progress():

    interviews = (
        Interview.query
        .filter_by(
            user_id=
            current_user.id
        )
        .filter(
            Interview.completed_at.isnot(None)
        )
        .order_by(
            Interview.completed_at.asc()
        )
        .all()
    )

    weak_topics = (
        WeakTopic.query
        .filter_by(
            user_id=
            current_user.id
        )
        .order_by(
            WeakTopic.weakness_score.desc()
        )
        .all()
    )

    chart_labels = [

        interview.completed_at.strftime(
            "%d %b"
        )

        for interview in interviews

        if interview.completed_at
    ]

    chart_scores = [

        interview.score or 0

        for interview in interviews
    ]

    return render_template(

        "progress.html",

        interviews=interviews,

        weak_topics=weak_topics,

        chart_labels=json.dumps(
            chart_labels
        ),

        chart_scores=json.dumps(
            chart_scores
        ),
    )


# ============================================================
# PREPARATION
# ============================================================

@app.route("/preparation")
@login_required
def preparation():

    weak_topics = (
        WeakTopic.query
        .filter_by(
            user_id=
            current_user.id
        )
        .order_by(
            WeakTopic.weakness_score.desc()
        )
        .limit(10)
        .all()
    )

    return render_template(

        "preparation.html",

        resources=RESOURCES,

        books=BOOKS,

        coding_platforms=
        CODING_PLATFORMS,

        weak_topics=weak_topics,
    )


# ============================================================
# PROFILE
# ============================================================

@app.route(
    "/profile",
    methods=["GET", "POST"]
)
@login_required
def profile():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        if len(name) < 2:

            flash(
                "Please enter a valid name.",
                "danger"
            )

        else:

            current_user.name = name

            db.session.commit()

            flash(
                "Profile updated.",
                "success"
            )

    return render_template(
        "profile.html"
    )


# ============================================================
# SPEECH TO TEXT
# ============================================================

@app.route(
    "/api/transcribe",
    methods=["POST"]
)
@login_required
def transcribe():

    audio = request.files.get(
        "audio"
    )

    if (
        not audio
        or not audio.filename
    ):

        return jsonify(
            {
                "error":
                "No audio file received."
            }
        ), 400

    try:

        text = (
            ai.transcribe_audio(
                audio
            )
        )

        return jsonify(
            {
                "text": text
            }
        )

    except AIServiceError as exc:

        return jsonify(
            {
                "error":
                str(exc)
            }
        ), 502


# ============================================================
# VOICE ANALYSIS HELPERS
# ============================================================

FILLER_WORDS = [
    "um",
    "uh",
    "erm",
    "hmm",
    "like",
    "basically",
    "actually",
    "literally",
    "you know",
    "i mean",
    "sort of",
    "kind of",
]


def count_filler_words(text):

    if not text:

        return {
            "total": 0,
            "words": {},
        }

    normalized = (
        text.lower()
        .replace("’", "'")
    )

    results = {}

    total = 0

    for filler in FILLER_WORDS:

        pattern = (
            r"\b"
            + re.escape(filler)
            + r"\b"
        )

        count = len(
            re.findall(
                pattern,
                normalized
            )
        )

        if count:

            results[filler] = count

            total += count

    return {
        "total": total,
        "words": results,
    }


def calculate_wpm(
    transcript,
    duration_seconds
):

    if (
        not transcript
        or duration_seconds <= 0
    ):

        return 0

    words = re.findall(
        r"\b[\w']+\b",
        transcript
    )

    minutes = (
        duration_seconds / 60
    )

    if minutes <= 0:

        return 0

    return round(
        len(words) / minutes,
        1
    )


def speaking_speed_feedback(wpm):

    if wpm <= 0:

        return "Not enough data"

    if wpm < 100:

        return (
            "Speaking pace was relatively slow. "
            "Try maintaining a natural conversational pace."
        )

    if wpm <= 160:

        return (
            "Speaking pace was within a conversational range."
        )

    return (
        "Speaking pace was relatively fast. "
        "Consider slowing slightly for clarity."
    )


def filler_feedback(total):

    if total == 0:

        return (
            "No common filler words were detected."
        )

    if total <= 3:

        return (
            "A small number of filler words were detected."
        )

    if total <= 7:

        return (
            "Several filler words were detected. "
            "Short pauses can help replace them."
        )

    return (
        "Frequent filler words were detected. "
        "Try using deliberate pauses instead."
    )


def silence_feedback(
    silence_seconds
):

    if silence_seconds <= 0:

        return (
            "No extended silence was reported."
        )

    if silence_seconds < 2:

        return (
            "Short pauses were detected."
        )

    if silence_seconds < 5:

        return (
            "Some longer pauses were detected."
        )

    return (
        "Several longer pauses were detected. "
        "Consider preparing key points before answering."
    )


# ============================================================
# VOICE ANALYSIS ROUTE
# ============================================================

@app.route(
    "/api/interview/<int:interview_id>/voice-analysis",
    methods=["POST"]
)
@login_required
def analyze_voice(interview_id):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        return jsonify(
            {
                "error":
                "Unauthorized interview."
            }
        ), 403

    audio = request.files.get(
        "audio"
    )

    transcript = (
        request.form.get(
            "transcript",
            ""
        )
        .strip()
    )

    # Browser should send duration
    try:

        duration = float(
            request.form.get(
                "duration",
                "0"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        duration = 0

    # Browser can send measured silence
    try:

        silence_seconds = float(
            request.form.get(
                "silence_seconds",
                "0"
            )
        )

    except (
        TypeError,
        ValueError
    ):

        silence_seconds = 0

    # --------------------------------------------------------
    # TRANSCRIBE IF TRANSCRIPT WAS NOT PROVIDED
    # --------------------------------------------------------

    if not transcript and audio:

        try:

            transcript = (
                ai.transcribe_audio(
                    audio
                )
            )

        except AIServiceError as exc:

            return jsonify(
                {
                    "error":
                    str(exc)
                }
            ), 502

    # --------------------------------------------------------
    # ANALYZE SPEECH
    # --------------------------------------------------------

    words = re.findall(
        r"\b[\w']+\b",
        transcript
    )

    word_count = len(words)

    wpm = calculate_wpm(
        transcript,
        duration
    )

    fillers = count_filler_words(
        transcript
    )

    result = {

        "type":
        "voice_analysis",

        "interview_id":
        interview.id,

        "duration_seconds":
        round(duration, 2),

        "answer_duration":
        f"{round(duration, 1)} seconds",

        "word_count":
        word_count,

        "speaking_speed_wpm":
        wpm,

        "speaking_speed_feedback":
        speaking_speed_feedback(wpm),

        "filler_words":
        fillers["words"],

        "filler_word_count":
        fillers["total"],

        "filler_feedback":
        filler_feedback(
            fillers["total"]
        ),

        "silence_seconds":
        round(
            silence_seconds,
            2
        ),

        "silence_feedback":
        silence_feedback(
            silence_seconds
        ),

        "voice_clarity":
        (
            "Clear transcription detected"
            if transcript
            else
            "Unable to determine"
        ),

        "transcript":
        transcript,
    }

    save_interview_analysis(
        interview.id,
        "voice",
        result
    )

    return jsonify(
        {
            "success": True,
            "analysis": result
        }
    )


# ============================================================
# VIDEO UPLOAD ROUTE
# ============================================================

@app.route(
    "/api/interview/<int:interview_id>/video",
    methods=["POST"]
)
@login_required
def upload_interview_video(interview_id):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        return jsonify(
            {
                "error":
                "Unauthorized interview."
            }
        ), 403

    video = request.files.get(
        "video"
    )

    if (
        not video
        or not video.filename
    ):

        return jsonify(
            {
                "error":
                "No video file received."
            }
        ), 400

    try:

        video_folder = (
            Path(
                app.config["UPLOAD_FOLDER"]
            ) / "videos"
        )

        video_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = (
            f"interview_"
            f"{interview.id}_"
            f"{current_user.id}_"
            f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            f".webm"
        )

        video_path = (
            video_folder / filename
        )

        video.save(
            str(video_path)
        )

        # ----------------------------------------------------
        # RUN VIDEO ANALYSIS
        # ----------------------------------------------------

        analysis = analyze_video_file(
            video_path
        )

        analysis["interview_id"] = (
            interview.id
        )

        analysis["filename"] = (
            filename
        )

        save_interview_analysis(
            interview.id,
            "video",
            analysis
        )

        return jsonify(
            {
                "success": True,

                "message":
                "Video uploaded and analyzed successfully.",

                "filename":
                filename,

                "interview_id":
                interview.id,

                "analysis":
                analysis,
            }
        ), 200

    except Exception as exc:

        return jsonify(
            {
                "error":
                "Failed to save or analyze interview video.",
                "details":
                str(exc)
            }
        ), 500


# ============================================================
# VIDEO ANALYSIS
# ============================================================

def analyze_video_file(
    video_path
):

    # --------------------------------------------------------
    # OPENCV NOT INSTALLED
    # --------------------------------------------------------

    if cv2 is None:

        return {

            "available": False,

            "message":
            "OpenCV is not installed. "
            "Install opencv-python to enable "
            "video analysis.",

            "frames_analyzed": 0,

            "face_detection_rate": 0,

            "eye_contact_percentage": 0,

            "looking_away_percentage": 0,

            "engagement_indicator":
            "Unavailable",

            "head_position":
            "Unavailable",

            "posture_feedback":
            "Unavailable",
        }

    # --------------------------------------------------------
    # LOAD FACE / EYE CLASSIFIERS
    # --------------------------------------------------------

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades
        + "haarcascade_frontalface_default.xml"
    )

    eye_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades
        + "haarcascade_eye.xml"
    )

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        return {

            "available": False,

            "message":
            "Unable to open the uploaded video.",

            "frames_analyzed": 0,
        }

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
    )

    fps = float(
        capture.get(
            cv2.CAP_PROP_FPS
        )
        or 0
    )

    if fps <= 0:

        fps = 30.0

    duration = (
        total_frames / fps
        if total_frames > 0
        else 0
    )

    frame_skip = max(
        1,
        int(fps / 2)
    )

    frames_analyzed = 0

    face_frames = 0

    eye_contact_frames = 0

    looking_away_frames = 0

    centered_frames = 0

    left_right_deviation = 0

    top_bottom_deviation = 0

    # --------------------------------------------------------
    # ANALYZE FRAMES
    # --------------------------------------------------------

    frame_index = 0

    while True:

        success, frame = (
            capture.read()
        )

        if not success:

            break

        frame_index += 1

        if (
            frame_index
            % frame_skip
            != 0
        ):

            continue

        frames_analyzed += 1

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60)
        )

        if len(faces) == 0:

            continue

        # Use largest detected face
        face = max(
            faces,
            key=lambda item:
            item[2] * item[3]
        )

        x, y, w, h = face

        face_frames += 1

        frame_height, frame_width = (
            gray.shape[:2]
        )

        face_center_x = (
            x + w / 2
        )

        face_center_y = (
            y + h / 2
        )

        screen_center_x = (
            frame_width / 2
        )

        screen_center_y = (
            frame_height / 2
        )

        horizontal_offset = (
            abs(
                face_center_x
                - screen_center_x
            )
            / frame_width
        )

        vertical_offset = (
            abs(
                face_center_y
                - screen_center_y
            )
            / frame_height
        )

        left_right_deviation += (
            horizontal_offset
        )

        top_bottom_deviation += (
            vertical_offset
        )

        if (
            horizontal_offset
            < 0.18
        ):

            centered_frames += 1

        face_roi = gray[
            y:y + h,
            x:x + w
        ]

        eyes = eye_cascade.detectMultiScale(
            face_roi,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(15, 15)
        )

        # ----------------------------------------------------
        # EYE CONTACT HEURISTIC
        # ----------------------------------------------------

        if len(eyes) >= 2:

            eye_contact_frames += 1

        else:

            looking_away_frames += 1

    capture.release()

    # --------------------------------------------------------
    # CALCULATE RESULTS
    # --------------------------------------------------------

    if frames_analyzed <= 0:

        return {

            "available": False,

            "message":
            "No usable video frames were detected.",

            "frames_analyzed": 0,

            "duration_seconds":
            round(duration, 2),
        }

    face_detection_rate = (
        face_frames
        / frames_analyzed
        * 100
    )

    eye_contact_percentage = (
        eye_contact_frames
        / frames_analyzed
        * 100
    )

    looking_away_percentage = (
        looking_away_frames
        / frames_analyzed
        * 100
    )

    centered_percentage = (
        centered_frames
        / max(
            face_frames,
            1
        )
        * 100
    )

    average_horizontal_deviation = (
        left_right_deviation
        / max(
            face_frames,
            1
        )
    )

    average_vertical_deviation = (
        top_bottom_deviation
        / max(
            face_frames,
            1
        )
    )

    # --------------------------------------------------------
    # HEAD POSITION
    # --------------------------------------------------------

    if centered_percentage >= 75:

        head_position = (
            "Mostly centered"
        )

    elif centered_percentage >= 50:

        head_position = (
            "Moderately centered"
        )

    else:

        head_position = (
            "Frequently off-center"
        )

    # --------------------------------------------------------
    # ENGAGEMENT INDICATOR
    # --------------------------------------------------------

    if face_detection_rate >= 85:

        engagement = (
            "Face remained visible for most "
            "of the interview."
        )

    elif face_detection_rate >= 60:

        engagement = (
            "Face was visible for a substantial "
            "part of the interview."
        )

    else:

        engagement = (
            "Face visibility was inconsistent."
        )

    # --------------------------------------------------------
    # POSTURE / HEAD FEEDBACK
    # --------------------------------------------------------

    if (
        average_vertical_deviation
        < 0.15
    ):

        posture_feedback = (
            "Head position was generally stable "
            "within the camera frame."
        )

    else:

        posture_feedback = (
            "Head position moved noticeably "
            "within the camera frame."
        )

    return {

        "available": True,

        "duration_seconds":
        round(
            duration,
            2
        ),

        "frames_analyzed":
        frames_analyzed,

        "face_detection_rate":
        round(
            face_detection_rate,
            1
        ),

        "eye_contact_percentage":
        round(
            eye_contact_percentage,
            1
        ),

        "looking_away_percentage":
        round(
            looking_away_percentage,
            1
        ),

        "engagement_indicator":
        engagement,

        "head_position":
        head_position,

        "posture_feedback":
        posture_feedback,

        "camera_centered_percentage":
        round(
            centered_percentage,
            1
        ),

        "feedback_note":
        (
            "These indicators are based on "
            "visible video patterns and are "
            "intended as interview feedback, "
            "not personality judgments."
        ),
    }


# ============================================================
# INTERVIEW ANALYSIS STORAGE
# ============================================================

def get_analysis_folder():

    folder = (
        Path(
            app.config["UPLOAD_FOLDER"]
        )
        / "analysis"
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return folder


def get_analysis_path(
    interview_id
):

    return (
        get_analysis_folder()
        / f"interview_{interview_id}_analysis.json"
    )


def load_interview_analysis(
    interview_id
):

    path = get_analysis_path(
        interview_id
    )

    if not path.exists():

        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (
        OSError,
        ValueError,
        TypeError
    ):

        return {}


def save_interview_analysis(
    interview_id,
    analysis_type,
    data
):

    path = get_analysis_path(
        interview_id
    )

    current = load_interview_analysis(
        interview_id
    )

    if not isinstance(
        current,
        dict
    ):

        current = {}

    current[
        analysis_type
    ] = data

    current[
        "updated_at"
    ] = datetime.utcnow().isoformat()

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            current,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# GET SAVED ANALYSIS
# ============================================================

@app.route(
    "/api/interview/<int:interview_id>/analysis",
    methods=["GET"]
)
@login_required
def get_interview_analysis(
    interview_id
):

    interview = db.session.get(
        Interview,
        interview_id
    )

    if (
        not interview
        or interview.user_id
        != current_user.id
    ):

        return jsonify(
            {
                "error":
                "Unauthorized interview."
            }
        ), 403

    return jsonify(
        {
            "success": True,

            "analysis":
            load_interview_analysis(
                interview.id
            ),
        }
    )


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(
    RequestEntityTooLarge
)
def too_large(_):

    flash(
        "The uploaded file is too large. "
        "Maximum size is 5 MB.",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for(
            "start_interview"
        )
    )


# ============================================================
# 404
# ============================================================

@app.errorhandler(404)
def not_found(_):

    return render_template(

        "error.html",

        code=404,

        message="Page not found."

    ), 404


# ============================================================
# 500
# ============================================================

@app.errorhandler(500)
def server_error(_):

    db.session.rollback()

    return render_template(

        "error.html",

        code=500,

        message=(
            "Something went wrong. "
            "Please try again."
        )

    ), 500


# ============================================================
# JSON HELPERS
# ============================================================

def json_dumps_safe(value):

    return json.dumps(
        value,
        ensure_ascii=False
    )


def json_loads_safe(
    value,
    fallback
):

    try:

        return json.loads(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return fallback


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        ),

        debug=(
            os.getenv(
                "FLASK_DEBUG",
                "0"
            )
            == "1"
        ),
    )