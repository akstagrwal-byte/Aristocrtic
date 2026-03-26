from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
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


class VerifyGeneratedCodeRequest(BaseModel):
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


@app.post("/codes/generate")
def codes_generate() -> dict:
    code = generate_ghs_code()
    return {"code": code.code, "created_at": code.created_at.isoformat()}


@app.post("/codes/verify")
def codes_verify(req: VerifyGeneratedCodeRequest) -> dict:
    normalized_code = req.code.strip().upper()
    exists = code_exists(normalized_code)
    return {"code": normalized_code, "exists": exists}


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
