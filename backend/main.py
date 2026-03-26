from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .services import (
    code_exists,
    consume_hold,
    create_run,
    create_session_token,
    execute_run,
    generate_ghs_code,
    issue_auth_code,
    list_generated_codes,
    refund_hold,
    register_user,
    reserve_credits,
    user_id_from_token,
    verify_auth_code,
    wallet_snapshot,
)
from .store import store

app = FastAPI(title="Aristocrtic GHS Backend", version="0.2.0")
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    name: str
    referral_code: str | None = None


class VerifyCodeRequest(BaseModel):
    code: str


class ReserveRequest(BaseModel):
    run_id: str


class RunCreateRequest(BaseModel):
    pass


class RunExecuteRequest(BaseModel):
    run_id: str
    country: str
    state: str
    city: str
    hold_id: str
    simulate_failure: bool = False


class CodeGenerateResponse(BaseModel):
    code: str
    created_at: str


class CodeVerifyResponse(BaseModel):
    code: str
    exists: bool
    message: str


def current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return user_id_from_token(credentials.credentials)
    except ValueError as err:
        raise HTTPException(status_code=401, detail=str(err)) from err


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def verification_portal() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GHS Code Verification</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; max-width: 720px; }
    input, button { padding: .6rem; font-size: 1rem; }
    #result { margin-top: 1rem; font-weight: 600; }
    #action-log { margin-top: .8rem; color: #0b57d0; white-space: pre-line; }
  </style>
</head>
<body>
  <h1>GHS Code Verification Portal</h1>
  <p>This website is connected to the backend store and can verify if a code exists.</p>
  <input id="code-input" placeholder="GHS-0000" />
  <button id="verify-btn">Verify code</button>
  <div id="result"></div>
  <div id="action-log"></div>

  <script>
    const btn = document.getElementById("verify-btn");
    const result = document.getElementById("result");
    const actionLog = document.getElementById("action-log");
    const input = document.getElementById("code-input");

    function runSpecificActionScript(code) {
      document.body.style.background = "#f4f8ff";
      actionLog.textContent =
        `Specific script executed for ${code}:\n` +
        "- Session action token prepared\n" +
        "- Follow-up automation step triggered\n" +
        "- Audit log marker recorded";
    }

    btn.addEventListener("click", async () => {
      const code = (input.value || "").trim().toUpperCase();
      if (!code) {
        result.textContent = "Enter a code first.";
        return;
      }

      const res = await fetch(`/codes/verify/${encodeURIComponent(code)}`);
      const payload = await res.json();
      result.textContent = payload.message;

      if (payload.exists) {
        runSpecificActionScript(payload.code);
      } else {
        actionLog.textContent = "No action script executed because code does not exist.";
      }
    });
  </script>
</body>
</html>
"""


@app.post("/testing/reset")
def testing_reset() -> dict:
    store.reset()
    return {"ok": True}


@app.post("/users/register")
def register(req: RegisterRequest) -> dict:
    user = register_user(req.name, req.referral_code)
    return {
        "user_id": user.user_id,
        "name": user.name,
        "referral_code": user.referral_code,
        "referred_by": user.referred_by,
    }


@app.post("/auth/code/create/{user_id}")
def create_auth_code(user_id: str) -> dict:
    try:
        code = issue_auth_code(user_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return {"code": code.code, "expires_at": code.expires_at.isoformat()}


@app.post("/auth/code/verify")
def auth_verify(req: VerifyCodeRequest) -> dict:
    try:
        user_id = verify_auth_code(req.code)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    token = create_session_token(user_id)
    return {"user_id": user_id, "authenticated": True, "access_token": token}


@app.get("/wallet/me")
def wallet(user_id: str = Depends(current_user_id)) -> dict:
    return wallet_snapshot(user_id)


@app.post("/runs")
def run_create(_: RunCreateRequest, user_id: str = Depends(current_user_id)) -> dict:
    run = create_run(user_id)
    return {"run_id": run.run_id, "status": run.status}


@app.post("/wallet/hold")
def wallet_hold(req: ReserveRequest, user_id: str = Depends(current_user_id)) -> dict:
    try:
        hold = reserve_credits(user_id, req.run_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    return {"hold_id": hold.hold_id, "amount": hold.amount}


@app.post("/runs/execute")
def run_execute(req: RunExecuteRequest, user_id: str = Depends(current_user_id)) -> dict:
    run = store.runs.get(req.run_id)
    if not run or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Run not found")

    run = execute_run(
        req.run_id,
        req.country,
        req.state,
        req.city,
        simulate_failure=req.simulate_failure,
    )

    if getattr(run.status, "value", run.status) == "VERIFIED_SUCCESS":
        consume_hold(req.hold_id)
    else:
        refund_hold(req.hold_id)

    return {
        "run_id": run.run_id,
        "status": run.status,
        "college": run.college,
        "error": run.error,
    }


@app.post("/codes/generate", response_model=CodeGenerateResponse)
def generate_code() -> dict:
    generated = generate_ghs_code()
    return {"code": generated.code, "created_at": generated.created_at.isoformat()}


@app.get("/codes/verify/{code}", response_model=CodeVerifyResponse)
def verify_code_exists(code: str) -> dict:
    normalized = code.upper()
    exists = code_exists(normalized)
    message = (
        "Code exist , test complete and add a specific and certain script to do some actions"
        if exists
        else "Code does not exist"
    )
    return {"code": normalized, "exists": exists, "message": message}


@app.get("/codes")
def list_codes() -> dict:
    return {
        "codes": [
            {"code": code.code, "created_at": code.created_at.isoformat()}
            for code in list_generated_codes()
        ]
    }
