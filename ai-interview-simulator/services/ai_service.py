import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

# ai_service.py:
# project_folder/
#     services/
#         ai_service.py

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env",
    override=True
)


# ============================================================
# ERROR CLASS
# ============================================================

class AIServiceError(Exception):
    pass


# ============================================================
# AI SERVICE
# ============================================================

class AIService:

    def __init__(self):

        self.api_key = os.getenv(
            "GROQ_API_KEY",
            ""
        )

        self.model = os.getenv(
            "GROQ_MODEL",
            "openai/gpt-oss-20b"
        )

        self.stt_model = os.getenv(
            "GROQ_STT_MODEL",
            "whisper-large-v3-turbo"
        )

        self.client = (
            Groq(api_key=self.api_key)
            if self.api_key
            else None
        )

    # ========================================================
    # REQUIRE GROQ CLIENT
    # ========================================================

    def _require_client(self):

        if not self.client:

            raise AIServiceError(
                "GROQ_API_KEY is missing. "
                "Add it to your .env file and restart the application."
            )

    # ========================================================
    # CHAT REQUEST
    # ========================================================

    def _chat(
        self,
        system,
        user,
        json_mode=False,
        max_tokens=1600
    ):

        self._require_client()

        if json_mode:

            system += """

IMPORTANT OUTPUT RULES:

Return ONLY one valid JSON object.

Do not use Markdown.

Do not use ```json.

Do not write anything before the JSON.

Do not write anything after the JSON.

The complete response must be valid JSON.
"""

        try:

            response = (
                self.client
                .chat
                .completions
                .create(
                    model=self.model,

                    messages=[
                        {
                            "role": "system",
                            "content": system
                        },
                        {
                            "role": "user",
                            "content": user
                        }
                    ],

                    temperature=0.4,

                    max_completion_tokens=max_tokens
                )
            )

            content = (
                response
                .choices[0]
                .message
                .content
                or ""
            )

        except Exception as exc:

            raise AIServiceError(
                f"AI service request failed: {exc}"
            ) from exc

        if not content.strip():

            raise AIServiceError(
                "The AI returned an empty response."
            )

        return content.strip()

    # ========================================================
    # PARSE JSON
    # ========================================================

    def _parse_json(self, content):

        if not content:
            raise AIServiceError(
                "The AI returned an empty structured response."
            )

        content = content.strip()

        # -----------------------------------------------
        # Attempt 1
        # -----------------------------------------------

        try:

            return json.loads(content)

        except json.JSONDecodeError:
            pass

        # -----------------------------------------------
        # Remove Markdown fences
        # -----------------------------------------------

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned
        )

        cleaned = cleaned.strip()

        # -----------------------------------------------
        # Attempt 2
        # -----------------------------------------------

        try:

            return json.loads(cleaned)

        except json.JSONDecodeError:
            pass

        # -----------------------------------------------
        # Extract JSON object
        # -----------------------------------------------

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if (
            start != -1
            and end != -1
            and end > start
        ):

            json_text = cleaned[
                start:end + 1
            ]

            try:

                return json.loads(
                    json_text
                )

            except json.JSONDecodeError:
                pass

        raise AIServiceError(
            "The AI returned an invalid structured response. "
            "Please try again."
        )

    # ========================================================
    # NORMALIZE TEXT
    # ========================================================

    def _normalize_topic(self, topic):

        if not topic:
            return ""

        topic = str(topic).strip().lower()

        topic = re.sub(
            r"[^a-z0-9+#.\- ]",
            "",
            topic
        )

        topic = re.sub(
            r"\s+",
            " ",
            topic
        )

        return topic.strip()

    # ========================================================
    # RECENT TOPICS
    # ========================================================

    def _get_recent_topics(
        self,
        previous_questions
    ):

        topics = []

        for question in previous_questions[-8:]:

            if not isinstance(
                question,
                dict
            ):
                continue

            topic = question.get(
                "topic",
                ""
            )

            normalized = self._normalize_topic(
                topic
            )

            if normalized:
                topics.append(
                    normalized
                )

        return topics

    # ========================================================
    # RECENT QUESTIONS
    # ========================================================

    def _get_recent_questions(
        self,
        previous_questions
    ):

        result = []

        for question in previous_questions[-12:]:

            if not isinstance(
                question,
                dict
            ):
                continue

            text = str(
                question.get(
                    "question",
                    ""
                )
            ).strip()

            if text:
                result.append(
                    text.lower()
                )

        return result

    # ========================================================
    # PREVIOUS WEAK TOPICS
    # ========================================================

    def _get_weak_topics(
        self,
        weak_topics
    ):

        result = []

        for item in weak_topics or []:

            if isinstance(
                item,
                dict
            ):

                topic = item.get(
                    "topic",
                    ""
                )

                weakness = item.get(
                    "score",
                    0
                )

            else:

                topic = str(item)
                weakness = 0

            topic = str(
                topic
            ).strip()

            if topic:

                result.append(
                    {
                        "topic": topic,
                        "weakness": weakness
                    }
                )

        return result

    # ========================================================
    # ADAPTIVE DIFFICULTY
    # ========================================================

    def _calculate_adaptive_difficulty(
        self,
        selected_difficulty,
        previous_questions,
        progress
    ):

        """
        Adaptive difficulty rules.

        Beginner:
            starts beginner and can move toward intermediate.

        Intermediate:
            can move beginner/intermediate/advanced.

        Advanced:
            can move intermediate/advanced/expert.

        Expert:
            remains advanced/expert.

        The AI is still instructed to respect the
        user's selected difficulty range.
        """

        selected = str(
            selected_difficulty or "Beginner"
        ).strip().lower()

        scores = []

        for question in previous_questions[-5:]:

            if not isinstance(
                question,
                dict
            ):
                continue

            score = question.get(
                "score"
            )

            try:

                if score is not None:
                    scores.append(
                        float(score)
                    )

            except (
                TypeError,
                ValueError
            ):
                pass

        # No previous performance
        if not scores:

            return selected_difficulty

        average = sum(scores) / len(scores)

        if selected == "beginner":

            if average >= 85:
                return "Intermediate"

            return "Beginner"

        if selected == "intermediate":

            if average >= 85:
                return "Advanced"

            if average < 45:
                return "Beginner"

            return "Intermediate"

        if selected == "advanced":

            if average >= 85:
                return "Expert"

            if average < 45:
                return "Intermediate"

            return "Advanced"

        if selected == "expert":

            if average < 50:
                return "Advanced"

            return "Expert"

        return selected_difficulty

    # ========================================================
    # SELECT TOPIC
    # ========================================================

    def _select_topic(
        self,
        previous_questions,
        weak_topics,
        branch,
        role,
        progress
    ):

        recent_topics = self._get_recent_topics(
            previous_questions
        )

        weak_candidates = []

        for item in self._get_weak_topics(
            weak_topics
        ):

            normalized = self._normalize_topic(
                item["topic"]
            )

            if normalized:

                weak_candidates.append(
                    (
                        normalized,
                        item["topic"],
                        item["weakness"]
                    )
                )

        # ----------------------------------------------------
        # WEAK TOPIC TARGETING
        # ----------------------------------------------------

        # Prefer the weakest topic that was not asked
        # immediately recently.

        for (
            normalized,
            original,
            weakness
        ) in weak_candidates:

            if normalized not in recent_topics:

                return str(
                    original
                ).strip()

        # ----------------------------------------------------
        # GENERAL TOPIC POOL
        # ----------------------------------------------------

        topic_pool = [

            "Programming Fundamentals",

            "C",

            "Java",

            "Python",

            "JavaScript",

            "Arrays",

            "Strings",

            "Recursion",

            "Searching",

            "Sorting",

            "Linked Lists",

            "Stack",

            "Queue",

            "Trees",

            "Graphs",

            "Heaps",

            "Hashing",

            "Object Oriented Programming",

            "DBMS",

            "SQL",

            "Operating Systems",

            "Computer Networks",

            "Computer Architecture",

            "Software Engineering",

            "Web Development",

            "Problem Solving",

            "Machine Learning",

            "Data Science",

            "Resume Based"

        ]

        # ----------------------------------------------------
        # REMOVE RECENT TOPICS
        # ----------------------------------------------------

        available = [

            topic

            for topic in topic_pool

            if self._normalize_topic(topic)
            not in recent_topics

        ]

        # ----------------------------------------------------
        # IF ALL TOPICS WERE USED
        # ----------------------------------------------------

        if not available:

            available = [

                topic

                for topic in topic_pool

                if self._normalize_topic(topic)
                not in recent_topics[-2:]

            ]

        # ----------------------------------------------------
        # DETERMINISTIC ROTATION
        # ----------------------------------------------------

        if available:

            index = (
                progress
                % len(available)
            )

            return available[index]

        return "Programming Fundamentals"

    # ========================================================
    # FOLLOW-UP DETECTION
    # ========================================================

    def _should_generate_follow_up(
        self,
        previous_questions
    ):

        if not previous_questions:
            return False

        last = previous_questions[-1]

        if not isinstance(
            last,
            dict
        ):
            return False

        score = last.get(
            "score"
        )

        try:

            score = float(score)

        except (
            TypeError,
            ValueError
        ):

            return False

        # Strong answers can receive a deeper
        # follow-up occasionally.

        if score >= 80:
            return True

        # Partial answers should also be followed up
        # so the interviewer can test understanding.

        if 45 <= score < 80:
            return True

        return False

    # ========================================================
    # GENERATE INTERVIEW QUESTION
    # ========================================================

    def generate_question(
        self,
        company,
        branch,
        role,
        difficulty,
        resume_text,
        previous_questions,
        weak_topics,
        progress
    ):

        # ----------------------------------------------------
        # Safety
        # ----------------------------------------------------

        if not isinstance(
            previous_questions,
            list
        ):

            previous_questions = []

        if not isinstance(
            weak_topics,
            list
        ):

            weak_topics = []

        if not isinstance(
            company,
            dict
        ):

            company = {
                "name": str(company or "")
            }

        # ----------------------------------------------------
        # ADAPTIVE DIFFICULTY
        # ----------------------------------------------------

        adaptive_difficulty = (
            self._calculate_adaptive_difficulty(
                selected_difficulty=difficulty,
                previous_questions=previous_questions,
                progress=progress
            )
        )

        # ----------------------------------------------------
        # SELECT TOPIC
        # ----------------------------------------------------

        forced_topic = self._select_topic(
            previous_questions=previous_questions,
            weak_topics=weak_topics,
            branch=branch,
            role=role,
            progress=progress
        )

        # ----------------------------------------------------
        # FOLLOW-UP
        # ----------------------------------------------------

        follow_up = (
            self._should_generate_follow_up(
                previous_questions
            )
        )

        previous_question = ""

        previous_answer = ""

        previous_score = ""

        if previous_questions:

            last = previous_questions[-1]

            if isinstance(
                last,
                dict
            ):

                previous_question = str(
                    last.get(
                        "question",
                        ""
                    )
                )

                previous_answer = str(
                    last.get(
                        "answer",
                        ""
                    )
                )

                previous_score = str(
                    last.get(
                        "score",
                        ""
                    )
                )

        # ----------------------------------------------------
        # COMPANY DATA
        # ----------------------------------------------------

        company_text = json.dumps(
            {
                "name": company.get(
                    "name",
                    ""
                ),

                "industry": company.get(
                    "industry",
                    ""
                ),

                "description": company.get(
                    "description",
                    ""
                ),

                "skills": company.get(
                    "skills",
                    []
                ),

                "technical_topics": company.get(
                    "technical_topics",
                    []
                ),

                "roles": company.get(
                    "roles",
                    []
                )
            },
            ensure_ascii=False
        )

        # ----------------------------------------------------
        # PREVIOUS QUESTIONS
        # ----------------------------------------------------

        previous_text = json.dumps(
            previous_questions[-12:],
            ensure_ascii=False
        )

        # ----------------------------------------------------
        # WEAK TOPICS
        # ----------------------------------------------------

        weak_text = json.dumps(
            weak_topics,
            ensure_ascii=False
        )

        # ----------------------------------------------------
        # SYSTEM PROMPT
        # ----------------------------------------------------

        system = """

You are an adaptive AI technical interviewer.

Your ONLY job is to generate ONE interview question.

You must NOT answer the question.

You must NOT provide the solution.

You must NOT provide hints.

You must NOT provide a rubric.

You must NOT provide an explanation.

============================================================
CORE INTERVIEW RULE
============================================================

Generate exactly ONE question.

The question must be suitable for:

- the candidate branch
- the selected job role
- the company context
- the candidate resume
- the adaptive difficulty
- the required topic
- previous interview performance

============================================================
REQUIRED TOPIC
============================================================

The application selects a REQUIRED TOPIC.

You MUST use that topic.

Do not replace it with another unrelated topic.

============================================================
ADAPTIVE DIFFICULTY
============================================================

The application may change the difficulty based on
previous answer scores.

If the candidate performs strongly:

Increase conceptual depth and complexity.

If the candidate performs poorly:

Reduce complexity while continuing to test the same
important concept where appropriate.

Do not make the question impossible.

============================================================
FOLLOW-UP QUESTIONS
============================================================

If FOLLOW_UP is true:

Create a meaningful follow-up to the previous question.

A follow-up may:

- ask the candidate to explain deeper
- ask for optimization
- ask about edge cases
- ask why their approach works
- ask about complexity
- ask for an example
- test a related concept

Do NOT simply repeat the previous question.

============================================================
PREVIOUS-INTERVIEW LEARNING
============================================================

Previous questions may contain scores and answers.

Use them to identify:

- weak concepts
- strong concepts
- repeated mistakes
- concepts that need deeper testing

Do not repeat an identical question.

============================================================
RESUME
============================================================

Use only information explicitly present in the resume.

Do not invent:

- companies
- projects
- internships
- skills
- certifications
- experience

If a resume contains a project or skill relevant to the
required topic, a resume-based question may be generated.

============================================================
COMPANY
============================================================

Use company information as context.

Do not claim that a company definitely asks a particular
question.

============================================================
CODING QUESTIONS
============================================================

If generating a coding question, include:

- problem statement
- constraints
- expected input
- expected output

Do not provide the solution.

============================================================
QUESTION QUALITY
============================================================

Avoid:

- duplicate questions
- trivial rewording
- unrelated topics
- multiple questions
- answers
- hints
- explanations

============================================================
OUTPUT
============================================================

Return exactly:

{
    "question": "...",
    "category": "...",
    "topic": "...",
    "difficulty": "...",
    "is_follow_up": true
}

The topic MUST match the required topic.

============================================================
"""

        # ----------------------------------------------------
        # USER PROMPT
        # ----------------------------------------------------

        user = f"""

COMPANY:

{company_text}


BRANCH:

{branch}


ROLE:

{role}


USER SELECTED DIFFICULTY:

{difficulty}


ADAPTIVE DIFFICULTY:

{adaptive_difficulty}


INTERVIEW QUESTION NUMBER:

{progress + 1}


============================================================
REQUIRED TOPIC
============================================================

{forced_topic}


============================================================
FOLLOW-UP REQUIRED
============================================================

{follow_up}


============================================================
PREVIOUS QUESTION
============================================================

{previous_question or "None"}


============================================================
PREVIOUS ANSWER
============================================================

{previous_answer or "None"}


============================================================
PREVIOUS SCORE
============================================================

{previous_score or "None"}


============================================================
RECENT TOPICS
============================================================

{json.dumps(
    self._get_recent_topics(
        previous_questions
    ),
    ensure_ascii=False
)}


============================================================
PREVIOUS QUESTIONS
============================================================

{previous_text}


============================================================
KNOWN WEAK TOPICS
============================================================

{weak_text}


============================================================
RESUME
============================================================

{
    resume_text[:30000]
    if resume_text
    else "No resume provided."
}


============================================================
FINAL INSTRUCTION
============================================================

Generate exactly ONE interview question.

The question MUST focus on:

{forced_topic}

Adaptive difficulty:

{adaptive_difficulty}

Follow-up:

{follow_up}

Do not generate an unrelated question.

Do not repeat an existing question.
"""

        # ----------------------------------------------------
        # AI REQUEST
        # ----------------------------------------------------

        data = self._parse_json(
            self._chat(
                system,
                user,
                json_mode=True,
                max_tokens=1400
            )
        )

        # ----------------------------------------------------
        # VALIDATE QUESTION
        # ----------------------------------------------------

        question_text = str(
            data.get(
                "question",
                ""
            )
        ).strip()

        if not question_text:

            raise AIServiceError(
                "AI did not generate a usable question."
            )

        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        normalized_question = re.sub(
            r"\s+",
            " ",
            question_text.lower()
        ).strip()

        recent_questions = (
            self._get_recent_questions(
                previous_questions
            )
        )

        if normalized_question in recent_questions:

            # We do not silently save a duplicate.
            raise AIServiceError(
                "AI generated a duplicate question. "
                "Please try generating the next question again."
            )

        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        category = str(
            data.get(
                "category",
                "Technical"
            )
        ).strip()

        if not category:
            category = "Technical"

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Python-selected topic is authoritative.
        # ----------------------------------------------------

        returned_difficulty = str(
            data.get(
                "difficulty",
                adaptive_difficulty
            )
        ).strip()

        if not returned_difficulty:

            returned_difficulty = (
                adaptive_difficulty
            )

        return {

            "question":
                question_text,

            "category":
                category[:80],

            "topic":
                forced_topic[:120],

            "difficulty":
                returned_difficulty[:40],

            "is_follow_up":
                bool(
                    data.get(
                        "is_follow_up",
                        follow_up
                    )
                )
        }

    # ========================================================
    # EVALUATE ANSWER
    # ========================================================

    def evaluate_answer(
        self,
        question,
        category,
        topic,
        difficulty,
        answer,
        resume_text
    ):

        system = """

You are an AI interview evaluator.

Evaluate ONLY the candidate's submitted answer.

Do not provide a complete model answer.

Evaluate:

- correctness
- relevance
- technical accuracy
- completeness
- explanation quality
- problem-solving approach

For behavioral answers evaluate:

- relevance
- clarity
- evidence
- structure

============================================================
CLASSIFICATION
============================================================

classification must be exactly one of:

"correct"

"partially correct"

"incorrect"

============================================================
SCORING
============================================================

All scores must be integers from 0 to 100.

============================================================
WEAK TOPICS
============================================================

Return topics that clearly need revision.

Do not randomly generate weak topics.

============================================================
OUTPUT
============================================================

Return exactly:

{
    "score": 0,
    "classification": "correct",
    "technical_accuracy": 0,
    "completeness": 0,
    "feedback": "...",
    "weak_topics": [],
    "needs_revision": false
}

Do not invent facts about the candidate.
"""

        user = f"""

QUESTION:

{question}


CATEGORY:

{category}


TOPIC:

{topic}


DIFFICULTY:

{difficulty}


CANDIDATE ANSWER:

{answer}


RESUME CONTEXT:

{
    resume_text[:12000]
    if resume_text
    else "No resume provided."
}
"""

        data = self._parse_json(
            self._chat(
                system,
                user,
                json_mode=True,
                max_tokens=1200
            )
        )

        # ----------------------------------------------------
        # CLASSIFICATION
        # ----------------------------------------------------

        classification = str(
            data.get(
                "classification",
                "incorrect"
            )
        ).lower().strip()

        if classification not in {
            "correct",
            "partially correct",
            "incorrect"
        }:

            classification = "incorrect"

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        try:

            score = int(
                data.get(
                    "score",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            score = 0

        # ----------------------------------------------------
        # TECHNICAL ACCURACY
        # ----------------------------------------------------

        try:

            technical_accuracy = int(
                data.get(
                    "technical_accuracy",
                    score
                )
            )

        except (
            TypeError,
            ValueError
        ):

            technical_accuracy = score

        # ----------------------------------------------------
        # COMPLETENESS
        # ----------------------------------------------------

        try:

            completeness = int(
                data.get(
                    "completeness",
                    score
                )
            )

        except (
            TypeError,
            ValueError
        ):

            completeness = score

        # ----------------------------------------------------
        # WEAK TOPICS
        # ----------------------------------------------------

        weak_topics = data.get(
            "weak_topics",
            []
        )

        if not isinstance(
            weak_topics,
            list
        ):

            weak_topics = []

        clean_weak_topics = []

        for weak_topic in weak_topics:

            value = str(
                weak_topic
            ).strip()

            if value:

                clean_weak_topics.append(
                    value[:120]
                )

        # ----------------------------------------------------
        # AUTOMATIC TOPIC FALLBACK
        # ----------------------------------------------------

        if (
            not clean_weak_topics
            and score < 60
        ):

            clean_weak_topics.append(
                str(topic)[:120]
            )

        # ----------------------------------------------------
        # FEEDBACK
        # ----------------------------------------------------

        feedback = str(
            data.get(
                "feedback",
                "Review this topic and try again."
            )
        ).strip()

        if not feedback:

            feedback = (
                "Review this topic and try again."
            )

        # ----------------------------------------------------
        # NEEDS REVISION
        # ----------------------------------------------------

        needs_revision = data.get(
            "needs_revision",
            classification != "correct"
        )

        if isinstance(
            needs_revision,
            str
        ):

            needs_revision = (
                needs_revision.lower()
                in {
                    "true",
                    "yes",
                    "1"
                }
            )

        else:

            needs_revision = bool(
                needs_revision
            )

        # ----------------------------------------------------
        # RETURN
        # ----------------------------------------------------

        return {

            "score": max(
                0,
                min(
                    100,
                    score
                )
            ),

            "classification":
                classification,

            "technical_accuracy": max(
                0,
                min(
                    100,
                    technical_accuracy
                )
            ),

            "completeness": max(
                0,
                min(
                    100,
                    completeness
                )
            ),

            "feedback":
                feedback,

            "weak_topics":
                clean_weak_topics[:5],

            "needs_revision":
                needs_revision
        }

    # ========================================================
    # FINAL INTERVIEW FEEDBACK
    # ========================================================

    def generate_feedback(
        self,
        payload
    ):

        system = """

You are an AI interview coach.

Generate a concise but useful final interview feedback report.

Use ONLY the supplied interview data.

Do not invent candidate experience.

============================================================
OUTPUT
============================================================

Return exactly:

{
    "overall_score": 0,
    "summary": "...",
    "performance": {},
    "strengths": [],
    "weaknesses": [],
    "recommended_topics": [],
    "improvement_plan": []
}

overall_score must be between 0 and 100.

performance must be an object containing category scores.

strengths must be an array.

weaknesses must be an array.

recommended_topics must be an array.

improvement_plan must be an array of actionable steps.
"""

        user = json.dumps(
            payload,
            ensure_ascii=False
        )

        data = self._parse_json(
            self._chat(
                system,
                user,
                json_mode=True,
                max_tokens=1800
            )
        )

        # ----------------------------------------------------
        # SCORE
        # ----------------------------------------------------

        try:

            overall_score = int(
                data.get(
                    "overall_score",
                    payload.get(
                        "overall_score",
                        0
                    )
                )
            )

        except (
            TypeError,
            ValueError
        ):

            overall_score = 0

        data["overall_score"] = max(
            0,
            min(
                100,
                overall_score
            )
        )

        # ----------------------------------------------------
        # SAFE DEFAULTS
        # ----------------------------------------------------

        if not isinstance(
            data.get("performance"),
            dict
        ):

            data["performance"] = (
                payload.get(
                    "performance",
                    {}
                )
            )

        if not isinstance(
            data.get("strengths"),
            list
        ):

            data["strengths"] = []

        if not isinstance(
            data.get("weaknesses"),
            list
        ):

            data["weaknesses"] = []

        if not isinstance(
            data.get("recommended_topics"),
            list
        ):

            data["recommended_topics"] = []

        if not isinstance(
            data.get("improvement_plan"),
            list
        ):

            data["improvement_plan"] = []

        return data

    # ========================================================
    # SPEECH TO TEXT
    # ========================================================

    def transcribe_audio(
        self,
        audio_file
    ):

        self._require_client()

        try:

            result = (
                self.client
                .audio
                .transcriptions
                .create(
                    file=(
                        audio_file.filename,
                        audio_file.stream,
                        audio_file.mimetype
                        or "audio/webm"
                    ),

                    model=self.stt_model,

                    language="en"
                )
            )

            text = getattr(
                result,
                "text",
                ""
            ) or ""

            if not text.strip():

                raise AIServiceError(
                    "No speech was detected in the recording."
                )

            return text.strip()

        except AIServiceError:

            raise

        except Exception as exc:

            raise AIServiceError(
                f"Speech transcription failed: {exc}"
            ) from exc