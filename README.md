# Video Trimmer / YouTube Shorts AI

This repository contains the backend API for downloading YouTube videos, uploading them to Supabase Storage, splitting them into Shorts, and storing the metadata in Supabase tables.

## Setup

1. Create a Python virtual environment.
2. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Copy the environment example and add your real Supabase values:
   ```bash
   copy .env.example .env
   ```
4. Fill in the real values:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

## Run locally

```bash
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Important

- Do not commit your real `.env` file.
- Keep all secrets in Vercel environment variables when deploying.
- The project uses Supabase Storage and Postgres tables, not local project folders.

## Deploy to Vercel

- Import this repo into Vercel.
- Set environment variables in Vercel Project Settings -> Environment Variables:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
- If deploying only the backend, use the backend folder as the app root.
- If deploying the frontend separately, add the API base URL as a frontend environment variable.
