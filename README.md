# Aristocrtic

Production-style scaffold for a **Tampermonkey + FastAPI** automation platform with connected modules:
- bot-style onboarding with one-time login code
- Telegram inline-keyboard bot that generates `GHS-XXXX` codes
- bearer-token auth session
- wallet credit gating with hold / consume / refund
- referral bonuses
- run orchestration pipeline
- Tampermonkey userscript client that calls the backend end-to-end

## Architecture (connected modules)
- `backend/main.py`: API contracts and auth-protected endpoints
- `backend/services.py`: business logic (auth, wallet, runs, referrals)
- `backend/store.py`: in-memory persistence (users, sessions, runs, holds)
- code verification API endpoints: `POST /codes/generate`, `GET /codes/verify/{code}`, `GET /codes`
- separate verification frontend: `frontend/index.html`, `frontend/app.js`, `frontend/styles.css` served at `GET /`
- `tampermonkey/ghs.user.js`: client runtime (onboard + run flow)
- `tests/test_flow.py`: API-level integration tests proving connectivity

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn bot:app --reload
```

## Tampermonkey setup
1. Install Tampermonkey in your browser.
2. Create a new script and paste `tampermonkey/ghs.user.js`.
3. Update `API` base URL and `@match` domain.
4. In browser console, run:
   - `GHSAutomation.onboard('your-name')`
   - `GHSAutomation.runGHSFlow('us','ca','san francisco')`

## Tests

```bash
PYTHONPATH=. pytest -q
```

## Docs
- Full workflow and implementation details: `WORKFLOW.md`
