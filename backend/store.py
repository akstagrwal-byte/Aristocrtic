from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .models import AuthCode, GeneratedCode, Referral, Run, User, Wallet, WalletHold


@dataclass
class InMemoryStore:
    users: Dict[str, User] = field(default_factory=dict)
    users_by_referral_code: Dict[str, str] = field(default_factory=dict)
    auth_codes: Dict[str, AuthCode] = field(default_factory=dict)
    wallets: Dict[str, Wallet] = field(default_factory=dict)
    holds: Dict[str, WalletHold] = field(default_factory=dict)
    runs: Dict[str, Run] = field(default_factory=dict)
    referrals: List[Referral] = field(default_factory=list)
    sessions: Dict[str, str] = field(default_factory=dict)  # token -> user_id
    generated_codes: Dict[str, GeneratedCode] = field(default_factory=dict)

    def reset(self) -> None:
        self.users.clear()
        self.users_by_referral_code.clear()
        self.auth_codes.clear()
        self.wallets.clear()
        self.holds.clear()
        self.runs.clear()
        self.referrals.clear()
        self.sessions.clear()
        self.generated_codes.clear()


store = InMemoryStore()
