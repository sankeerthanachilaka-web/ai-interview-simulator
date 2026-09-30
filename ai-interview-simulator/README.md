# AI Interview Simulator

A Flask + SQLite + Groq application for adaptive technical interview practice.

## Features

- Registration, login, secure password hashing and session authentication
- SQLite database automatically created at first startup
- Company library with configurable preparation profiles
- Branch, job role and difficulty selection
- PDF/DOCX resume extraction
- AI-generated questions using company, branch, role, difficulty, resume, previous questions and weak topics
- AI answer evaluation with score, classification, feedback and weak-topic tracking
- Incorrect/low-scoring topics prioritized in future interviews
- Typing interview mode
- Voice interview mode with browser microphone recording and Groq Whisper transcription
- Video interview interface with browser camera preview; this version intentionally does not pretend to process/upload video
- Final feedback report
- Interview history
- Progress chart
- Preparation hub with documentation, books and coding platforms
- CSRF protection, upload validation, size limits and authentication checks

## Technology

- Python 3.10+
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF
- SQLite
- Groq Python SDK
- pypdf
- python-docx
- Bootstrap 5 + Bootstrap Icons
- Chart.js

## Folder structure

```text
ai-interview-simulator/
├── app.py
├── config.py
├── models.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── services/
│   ├── __init__.py
│   ├── ai_service.py
│   ├── data.py
│   ├── interview_service.py
│   └── resume_service.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── companies.html
│   ├── company_detail.html
│   ├── interview_setup.html
│   ├── interview.html
│   ├── feedback.html
│   ├── history.html
│   ├── progress.html
│   ├── preparation.html
│   ├── profile.html
│   └── error.html
├── static/
│   ├── css/style.css
│   └── js/
│       ├── main.js
│       ├── interview.js
│       └── voice.js
├── uploads/.gitkeep
└── instance/.gitkeep
```

## Installation

### Windows PowerShell

```powershell
cd ai-interview-simulator
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS/Linux

```bash
cd ai-interview-simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment setup

Copy `.env.example` to `.env`.

```env
SECRET_KEY=replace-with-a-long-random-secret
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_STT_MODEL=whisper-large-v3-turbo
MAX_QUESTIONS=10
FLASK_DEBUG=1
PORT=5000
```

Do not commit `.env`.

## Database

No manual database creation is needed.

When `app.py` starts, `db.create_all()` creates the SQLite database and tables automatically at:

```text
instance/interview_simulator.db
```

## Run

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## How question generation works

For each question the AI receives:

- selected company profile
- branch
- target role
- difficulty
- extracted resume text, when available
- previous questions in the current interview
- weak topics from previous interviews
- interview progress

The prompt explicitly instructs the model to ask one question and not reveal its answer before the candidate attempts it.

## Resume upload

PDF text is extracted with `pypdf`. DOCX text is extracted with `python-docx`.

The application accepts `.doc` in the upload validation list but does not pretend that legacy binary DOC extraction is implemented. Upload a PDF or DOCX for automatic extraction.

Resume text is stored in SQLite so it can be reused by later interviews.

## Interview modes

### Typing

Type the answer and submit.

### Voice

The browser records microphone audio. The recording is uploaded to the Flask backend and sent to Groq Whisper for transcription. The transcript is placed in the answer box so you can review it before submission.

If the browser refuses microphone access, check browser permissions and use localhost/HTTPS as required by your browser.

### Video

The application opens a camera preview. This project does not claim to process video answers. A text answer box remains available for evaluation.

## Answer evaluation

The AI returns structured JSON containing:

- score
- classification
- technical accuracy
- completeness
- feedback
- weak topics
- revision flag

The question and evaluation are saved.

## Weak-topic revision

Low-scoring topics are stored in the `weak_topics` table. Future question prompts include these topics, allowing the model to revisit concepts with a related or rephrased question rather than mechanically repeating the same wording.

## Coding questions

The AI can generate coding questions. This version evaluates submitted code as text through the AI and does not execute arbitrary candidate code on the Flask server.

For production-grade code execution, use a dedicated isolated sandbox/container service. Do not execute untrusted candidate code directly inside the web process.

## Troubleshooting

### "GROQ_API_KEY is missing"

Create `.env`, add your key, and restart Flask.

### AI request errors

Check your API key, model ID, network connection and provider limits. The model is configurable through `GROQ_MODEL`.

### Microphone errors

Allow microphone access in the browser. The application records in the browser and sends the recording to the backend for transcription.

### Resume extraction failed

Use a text-based PDF or DOCX. Scanned image-only PDFs may need OCR, which is not included in this project.

### Database reset

Stop Flask and delete:

```text
instance/interview_simulator.db
```

The database will be recreated on the next start. This deletes local interview history.

## Current provider note

The default model is `openai/gpt-oss-20b`, and the speech-to-text model is `whisper-large-v3-turbo`. Both are configurable in `.env`.
