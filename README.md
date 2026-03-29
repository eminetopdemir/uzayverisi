# SatComm Monitor

## Secure Remote Alert

This project includes a backend-controlled cinematic emergency alert channel for the dashboard.

### Backend secret

Set the alert secret on the backend host before starting FastAPI:

```bash
export SATCOMM_ALERT_SECRET="replace-with-a-long-random-secret"
cd backend
uvicorn main:app --reload --port 8000
```

The secret is validated only on the backend. It is never exposed to the frontend bundle.

### Trigger from a phone

Send an authorized request to the backend from any device on the same network or through your deployed endpoint:

```bash
curl -X POST http://YOUR_HOST:8000/trigger-storm \
	-H "Authorization: Bearer replace-with-a-long-random-secret"
```

You can also open the stealth mobile controller in a browser:

```text
http://YOUR_FRONTEND_HOST:5173/remote-control?token=replace-with-a-long-random-secret
```

The page renders a single dark-theme trigger button and sends a silent `POST /trigger-storm` request.

### Polling behavior

The React dashboard polls `GET /alert-status` every second. When an alert is active, the UI shows a full-screen cinematic overlay for 3 seconds and then clears automatically.

### Endpoints

- `POST /trigger-alert`
	- Backward-compatible secure trigger endpoint
- `POST /trigger-storm`
	- Requires `Authorization: Bearer <secret>`
	- Starts a 3-second alert window
- `GET /alert-status`
	- Returns current alert state for frontend polling
