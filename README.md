# Meeting Intelligence & Accountability System

An AI-powered system that converts meeting audio into structured, evidence-backed intelligence.

## Core Pipeline

Meeting Audio / Video
→ Speech-to-Text
→ Speaker Identification
→ Transcript
→ AI Understanding
→ Decisions and Commitments
→ Evidence and Confidence
→ Cross-Meeting Memory
→ Accountability Tracking

## Technology Stack

- Backend: Python and FastAPI
- Frontend: Next.js, React, and TypeScript
- Database: PostgreSQL with pgvector
- AI: Local Ollama models
- Speech processing: Faster-Whisper and speaker diarization

## Project Structure

- `backend/` — FastAPI application and Python dependencies
- `frontend/` — Next.js web application
- `app/` — Additional backend code; purpose still to be verified

## Backend Setup

From the project root:

    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Configure `backend/.env` using `backend/.env.example` as a guide. Never commit real credentials.

Start the API from the `backend` directory:

    uvicorn app.main:app --reload

API documentation: http://127.0.0.1:8000/docs

## Frontend Setup

    cd frontend
    npm install
    npm run dev

Configure the frontend environment variables before starting the application.

## Security

Never commit API keys, database credentials, access tokens, private meeting recordings, or local environment files.
