
# Football Social Intelligence

Football Social Intelligence is a web-based analytics
platform for monitoring and analyzing the social media
performance of Polish football clubs.

## Tech Stack

- Frontend: Next.js, React, TypeScript, Tailwind CSS
- Backend: Python, FastAPI
- Database: MySQL / MariaDB
- Future AI: Video analysis and machine learning

## Current Features

- Database of 49 Polish football clubs
- FastAPI REST API
- MySQL integration
- Club directory
- Search and filtering
- Dark Analytics interface

## Planned Features

- TikTok video statistics
- Historical follower tracking
- Performance dashboards
- Viral Radar
- AI Content Predictor
- Matchday Impact

## Development

Frontend:
cd frontend
npm install
npm run dev

Backend:
cd backend
python -m pip install fastapi uvicorn sqlalchemy pymysql python-dotenv

python -m uvicorn main:app --reload --port 8000

## Status

FSI v0.7 - Development