from collections import defaultdict
from datetime import datetime

from models import db, WeakTopic


# ============================================================
# CALCULATE INTERVIEW SCORE
# ============================================================

def calculate_interview_score(questions):
    """
    Calculate the average score of all answered questions.
    """

    scored = [
        q.score
        for q in questions
        if q.score is not None
    ]

    if not scored:
        return 0

    return round(
        sum(scored) / len(scored),
        1
    )


# ============================================================
# GET CATEGORY SCORES
# ============================================================

def calculate_category_scores(questions):
    """
    Calculate average score for each interview category.
    """

    category_scores = defaultdict(list)

    for question in questions:

        if question.score is None:
            continue

        category = (
            question.category
            or "Technical"
        )

        category_scores[category].append(
            question.score
        )

    return {
        category: round(
            sum(scores) / len(scores),
            1
        )
        for category, scores
        in category_scores.items()
        if scores
    }


# ============================================================
# UPDATE WEAK TOPICS
# ============================================================

def update_weak_topics(
    user_id,
    topic,
    subject,
    score,
    weak_topics=None
):
    """
    Store and update topics where the user is weak.

    A lower answer score produces a higher
    weakness_score.
    """

    topics = []

    if topic:
        topics.append(topic)

    for item in (
        weak_topics or []
    ):
        if str(item).strip():
            topics.append(
                str(item)
            )

    # Remove duplicates while preserving order
    unique_topics = list(
        dict.fromkeys(
            item.strip()
            for item in topics
            if item.strip()
        )
    )

    for item in unique_topics[:6]:

        normalized = item[:120]

        if not normalized:
            continue

        try:
            numeric_score = float(
                score or 0
            )
        except (
            TypeError,
            ValueError
        ):
            numeric_score = 0

        numeric_score = max(
            0,
            min(
                100,
                numeric_score
            )
        )

        weakness = (
            100 - numeric_score
        )

        existing = (
            WeakTopic.query
            .filter_by(
                user_id=user_id,
                topic=normalized
            )
            .first()
        )

        if existing:

            # Previous weakness has slightly
            # more weight than the latest result.
            existing.weakness_score = round(
                (
                    existing.weakness_score * 0.65
                    +
                    weakness * 0.35
                ),
                1
            )

            if subject:
                existing.subject = subject

            existing.last_seen = (
                datetime.utcnow()
            )

        else:

            db.session.add(
                WeakTopic(

                    user_id=user_id,

                    topic=normalized,

                    subject=(
                        subject
                        or "Technical"
                    ),

                    weakness_score=round(
                        weakness,
                        1
                    ),

                    last_seen=datetime.utcnow(),
                )
            )

    db.session.commit()


# ============================================================
# GET WEAK TOPICS
# ============================================================

def get_weak_topics(
    user_id,
    limit=8
):
    """
    Return the user's weakest topics first.
    """

    return (
        WeakTopic.query
        .filter_by(
            user_id=user_id
        )
        .order_by(
            WeakTopic.weakness_score.desc()
        )
        .limit(limit)
        .all()
    )


# ============================================================
# GET WEAK TOPIC DATA
# ============================================================

def get_weak_topic_data(
    user_id,
    limit=8
):
    """
    Convert WeakTopic database objects into
    dictionaries suitable for AI prompts.
    """

    topics = get_weak_topics(
        user_id,
        limit
    )

    return [
        {
            "topic": topic.topic,
            "subject": topic.subject,
            "score": topic.weakness_score,
        }
        for topic in topics
    ]


# ============================================================
# BUILD QUESTION HISTORY
# ============================================================

def build_question_history(
    questions
):
    """
    Convert database questions into the
    structure expected by AIService.
    """

    return [
        {
            "question": q.question_text,
            "category": q.category,
            "topic": q.topic,
            "difficulty": q.difficulty,
            "score": q.score,
        }
        for q in questions
    ]


# ============================================================
# BUILD FEEDBACK PAYLOAD
# ============================================================

def build_feedback_payload(
    interview,
    questions
):
    """
    Build complete interview data for
    final AI feedback.
    """

    scores = [
        q.score
        for q in questions
        if q.score is not None
    ]

    performance = (
        calculate_category_scores(
            questions
        )
    )

    weak = []
    strong = []

    # --------------------------------------------------------
    # FIND WEAK AND STRONG TOPICS
    # --------------------------------------------------------

    for question in questions:

        if question.score is None:
            continue

        topic = (
            question.topic
            or "General"
        )

        if question.score < 60:

            weak.append(topic)

        elif question.score >= 80:

            strong.append(topic)

    # --------------------------------------------------------
    # OVERALL SCORE
    # --------------------------------------------------------

    overall = (
        round(
            sum(scores) / len(scores),
            1
        )
        if scores
        else 0
    )

    weak = list(
        dict.fromkeys(
            weak
        )
    )

    strong = list(
        dict.fromkeys(
            strong
        )
    )

    # --------------------------------------------------------
    # FALLBACK FEEDBACK
    # --------------------------------------------------------

    fallback = {

        "overall_score":
            overall,

        "summary":
            (
                "Interview completed. "
                "Review the question-level "
                "feedback and weak topics "
                "below."
            ),

        "performance":
            performance,

        "strengths":
            strong[:5],

        "weaknesses":
            weak[:5],

        "recommended_topics":
            weak[:7],

        "improvement_plan":
            [
                (
                    "Review the weakest "
                    "topics from this interview."
                ),

                (
                    "Practice two or three "
                    "related coding or "
                    "conceptual problems."
                ),

                (
                    "Repeat another mock "
                    "interview after revision."
                ),
            ],
    }

    # --------------------------------------------------------
    # QUESTION DATA
    # --------------------------------------------------------

    question_data = []

    for q in questions:

        question_data.append(

            {
                "question":
                    q.question_text,

                "topic":
                    q.topic
                    or "General",

                "category":
                    q.category
                    or "Technical",

                "difficulty":
                    q.difficulty
                    or interview.difficulty,

                "score":
                    q.score
                    if q.score is not None
                    else 0,

                "feedback":
                    q.evaluation
                    or "",

                "answer":
                    q.user_answer
                    or "",

                "classification":
                    (
                        "correct"
                        if q.is_correct
                        else "incorrect"
                    ),
            }
        )

    # --------------------------------------------------------
    # FINAL PAYLOAD
    # --------------------------------------------------------

    return {

        "company":
            interview.company,

        "branch":
            interview.branch,

        "role":
            interview.role,

        "difficulty":
            interview.difficulty,

        "mode":
            interview.mode,

        "overall_score":
            overall,

        "performance":
            performance,

        "questions":
            question_data,

        "strengths":
            strong[:5],

        "weaknesses":
            weak[:5],

        "recommended_topics":
            weak[:7],

        "fallback_feedback":
            fallback,
    }


# ============================================================
# BUILD NEXT QUESTION CONTEXT
# ============================================================

def build_next_question_prompt_context(
    questions
):
    """
    Return previous-question information
    for adaptive question generation.
    """

    return [
        {
            "question":
                q.question_text,

            "topic":
                q.topic,

            "category":
                q.category,

            "difficulty":
                q.difficulty,

            "score":
                q.score,
        }

        for q in questions
    ]


# ============================================================
# DETERMINE ADAPTIVE DIFFICULTY
# ============================================================

def determine_adaptive_difficulty(
    questions,
    current_difficulty
):
    """
    Determine the next difficulty from recent
    interview performance.

    This is deliberately conservative so that
    one unusual answer does not immediately
    change the entire interview level.
    """

    answered = [
        q
        for q in questions
        if q.score is not None
    ]

    if len(answered) < 2:
        return current_difficulty

    recent = answered[-3:]

    scores = [
        q.score
        for q in recent
        if q.score is not None
    ]

    if not scores:
        return current_difficulty

    average = (
        sum(scores) / len(scores)
    )

    levels = [
        "Beginner",
        "Intermediate",
        "Advanced",
        "Expert",
    ]

    if current_difficulty not in levels:
        return current_difficulty

    index = levels.index(
        current_difficulty
    )

    # Strong recent performance
    if average >= 85:

        return levels[
            min(
                index + 1,
                len(levels) - 1
            )
        ]

    # Weak recent performance
    if average < 45:

        return levels[
            max(
                index - 1,
                0
            )
        ]

    return current_difficulty


# ============================================================
# DETERMINE QUESTION PROGRESS
# ============================================================

def get_interview_progress(
    questions,
    max_questions
):
    """
    Return useful progress information
    for adaptive interview logic.
    """

    answered = [
        q
        for q in questions
        if q.user_answer is not None
    ]

    total = len(questions)

    answered_count = len(
        answered
    )

    remaining = max(
        0,
        max_questions
        - answered_count
    )

    percentage = (
        round(
            (
                answered_count
                / max_questions
            ) * 100
        )
        if max_questions > 0
        else 0
    )

    return {

        "answered":
            answered_count,

        "generated":
            total,

        "remaining":
            remaining,

        "percentage":
            percentage,
    }


# ============================================================
# FIND MOST RECENT WEAK TOPICS
# ============================================================

def get_recent_weak_topics(
    questions,
    limit=5
):
    """
    Find topics associated with the user's
    lowest recent scores.
    """

    scored = [
        q
        for q in questions
        if q.score is not None
    ]

    scored.sort(
        key=lambda q: q.score
    )

    topics = []

    for question in scored:

        topic = (
            question.topic
            or "General"
        )

        if topic not in topics:

            topics.append(
                topic
            )

        if len(topics) >= limit:
            break

    return topics


# ============================================================
# FIND STRONG TOPICS
# ============================================================

def get_strong_topics(
    questions,
    limit=5
):
    """
    Find topics where the user has
    demonstrated strong performance.
    """

    scored = [
        q
        for q in questions
        if q.score is not None
    ]

    scored.sort(
        key=lambda q: q.score,
        reverse=True
    )

    topics = []

    for question in scored:

        if question.score < 80:
            continue

        topic = (
            question.topic
            or "General"
        )

        if topic not in topics:

            topics.append(
                topic
            )

        if len(topics) >= limit:
            break

    return topics


# ============================================================
# BUILD ADAPTIVE INTERVIEW CONTEXT
# ============================================================

def build_adaptive_context(
    questions,
    current_difficulty,
    max_questions
):
    """
    Create a compact context object containing
    the user's current interview performance.
    """

    progress = get_interview_progress(
        questions,
        max_questions
    )

    adaptive_difficulty = (
        determine_adaptive_difficulty(
            questions,
            current_difficulty
        )
    )

    recent_weak_topics = (
        get_recent_weak_topics(
            questions,
            limit=5
        )
    )

    strong_topics = (
        get_strong_topics(
            questions,
            limit=5
        )
    )

    return {

        "progress":
            progress,

        "current_difficulty":
            current_difficulty,

        "adaptive_difficulty":
            adaptive_difficulty,

        "recent_weak_topics":
            recent_weak_topics,

        "strong_topics":
            strong_topics,

        "previous_questions":
            build_next_question_prompt_context(
                questions
            ),
    }