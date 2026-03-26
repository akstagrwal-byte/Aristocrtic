from __future__ import annotations

from datetime import datetime, timezone
from random import randint
from secrets import token_urlsafe

from .models import (
    AuthCode,
    GeneratedCode,
    Referral,
    Run,
    RunStatus,
    User,
    Wallet,
    WalletHold,
    expiry,
    make_auth_code,
    make_hold_id,
    make_referral_code,
    make_run_id,
    make_user_id,
)
from .store import store

RUN_COST = 10
REFERRAL_SIGNUP_BONUS = 4
REFERRAL_SUCCESS_BONUS = 8


def register_user(name: str, referral_code: str | None = None) -> User:
    user = User(user_id=make_user_id(), name=name, referral_code=make_referral_code())
    store.users[user.user_id] = user
    store.users_by_referral_code[user.referral_code] = user.user_id
    store.wallets[user.user_id] = Wallet(user_id=user.user_id, available_credits=0)

    if referral_code:
        referrer_id = store.users_by_referral_code.get(referral_code)
        if referrer_id and referrer_id != user.user_id:
            user.referred_by = referrer_id
            store.referrals.append(
                Referral(referrer_user_id=referrer_id, referred_user_id=user.user_id)
            )
            store.wallets[user.user_id].available_credits += REFERRAL_SIGNUP_BONUS
    return user


def issue_auth_code(user_id: str) -> AuthCode:
    if user_id not in store.users:
        raise ValueError("Unknown user")
    code = make_auth_code()
    auth_code = AuthCode(code=code, user_id=user_id, expires_at=expiry())
    store.auth_codes[code] = auth_code
    return auth_code


def verify_auth_code(code: str) -> str:
    auth_code = store.auth_codes.get(code)
    if not auth_code:
        raise ValueError("Invalid code")
    if auth_code.consumed:
        raise ValueError("Code already used")
    if auth_code.expires_at < datetime.now(timezone.utc):
        raise ValueError("Code expired")
    auth_code.consumed = True
    return auth_code.user_id


def create_session_token(user_id: str) -> str:
    token = token_urlsafe(24)
    store.sessions[token] = user_id
    return token


def user_id_from_token(token: str) -> str:
    user_id = store.sessions.get(token)
    if not user_id:
        raise ValueError("Invalid or expired token")
    return user_id


def reserve_credits(user_id: str, run_id: str) -> WalletHold:
    wallet = store.wallets[user_id]
    if wallet.available_credits < RUN_COST:
        raise ValueError("Insufficient credits")
    wallet.available_credits -= RUN_COST
    wallet.locked_credits += RUN_COST
    hold = WalletHold(hold_id=make_hold_id(), user_id=user_id, run_id=run_id, amount=RUN_COST)
    store.holds[hold.hold_id] = hold
    return hold


def consume_hold(hold_id: str) -> None:
    hold = store.holds[hold_id]
    if hold.released:
        return
    wallet = store.wallets[hold.user_id]
    wallet.locked_credits -= hold.amount
    hold.released = True


def refund_hold(hold_id: str) -> None:
    hold = store.holds[hold_id]
    if hold.released:
        return
    wallet = store.wallets[hold.user_id]
    wallet.locked_credits -= hold.amount
    wallet.available_credits += hold.amount
    hold.released = True


def create_run(user_id: str) -> Run:
    run = Run(run_id=make_run_id(), user_id=user_id, status=RunStatus.AUTHENTICATED)
    store.runs[run.run_id] = run
    return run


def execute_run(
    run_id: str,
    country: str,
    state: str,
    city: str,
    simulate_failure: bool = False,
) -> Run:
    run = store.runs[run_id]
    run.status = RunStatus.CREDITS_RESERVED
    run.country = country
    run.state = state
    run.city = city

    run.status = RunStatus.RUN_STARTED
    run.status = RunStatus.LOCATION_SET
    run.college = pick_college(country, state, city)
    run.status = RunStatus.COLLEGE_SELECTED
    run.status = RunStatus.APPLICATION_STARTED
    run.status = RunStatus.DOCUMENT_UPLOADED

    if simulate_failure:
        run.status = RunStatus.FAILED_FINAL
        run.error = "Submission verification failed"
        return run

    run.status = RunStatus.VERIFIED_SUCCESS
    qualify_referral_if_needed(run.user_id)
    return run


def pick_college(country: str, state: str, city: str) -> str:
    return f"{city.title()} Central College ({state.upper()}, {country.upper()})"


def qualify_referral_if_needed(referred_user_id: str) -> None:
    for referral in store.referrals:
        if referral.referred_user_id == referred_user_id and not referral.rewarded:
            referral.qualified = True
            referral.rewarded = True
            store.wallets[referral.referrer_user_id].available_credits += REFERRAL_SUCCESS_BONUS


def wallet_snapshot(user_id: str) -> dict:
    wallet = store.wallets[user_id]
    return {
        "available_credits": wallet.available_credits,
        "locked_credits": wallet.locked_credits,
        "run_cost": RUN_COST,
    }


def generate_ghs_code() -> GeneratedCode:
    """Create and persist a unique GHS code in GHS-XXXX format."""
    while True:
        code = f"GHS-{randint(0, 9999):04d}"
        if code not in store.generated_codes:
            record = GeneratedCode(code=code)
            store.generated_codes[code] = record
            return record


def code_exists(code: str) -> bool:
    return code.strip().upper() in store.generated_codes
