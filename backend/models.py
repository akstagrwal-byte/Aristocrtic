from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class RunStatus(str, Enum):
    INIT = "INIT"
    AUTHENTICATED = "AUTHENTICATED"
    CREDIT_INSUFFICIENT = "CREDIT_INSUFFICIENT"
    CREDITS_RESERVED = "CREDITS_RESERVED"
    RUN_STARTED = "RUN_STARTED"
    LOCATION_SET = "LOCATION_SET"
    COLLEGE_SELECTED = "COLLEGE_SELECTED"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    FAILED_FINAL = "FAILED_FINAL"


@dataclass
class User:
    user_id: str
    name: str
    referral_code: str
    referred_by: Optional[str] = None


@dataclass
class AuthCode:
    code: str
    user_id: str
    expires_at: datetime
    consumed: bool = False


@dataclass
class Wallet:
    user_id: str
    available_credits: int = 0
    locked_credits: int = 0


@dataclass
class WalletHold:
    hold_id: str
    user_id: str
    run_id: str
    amount: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    released: bool = False


@dataclass
class Run:
    run_id: str
    user_id: str
    status: RunStatus = RunStatus.INIT
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    college: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None


@dataclass
class Referral:
    referrer_user_id: str
    referred_user_id: str
    qualified: bool = False
    rewarded: bool = False


def make_user_id() -> str:
    return f"usr_{uuid4().hex[:10]}"


def make_run_id() -> str:
    return f"run_{uuid4().hex[:10]}"


def make_hold_id() -> str:
    return f"hold_{uuid4().hex[:10]}"


def make_referral_code() -> str:
    return uuid4().hex[:8].upper()


def make_auth_code() -> str:
    return uuid4().hex[:6].upper()


def expiry(minutes: int = 10) -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)
