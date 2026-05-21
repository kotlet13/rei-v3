# Archived Legacy UI

This directory is kept only as a reference snapshot from 2026-05-19.

Do not run this UI as the current REI-v3 interface. Its API client still targets the old compatibility endpoints:

- `GET /api/v1/characters`
- `POST /api/v1/simulate`
- `POST /api/v1/rei-cycle`

The active UI is:

- `app/frontend/src/App.tsx`

The active backend contract is:

- `GET /api/v1/version`
- `/api/v1/playground/*`
