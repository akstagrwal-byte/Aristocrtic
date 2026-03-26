from fastapi.testclient import TestClient

from backend.main import app


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_full_connected_success_flow_with_referral_reward():
    client = TestClient(app)
    client.post("/testing/reset")

    referrer = client.post("/users/register", json={"name": "referrer"}).json()
    referred = client.post(
        "/users/register",
        json={"name": "referred", "referral_code": referrer["referral_code"]},
    ).json()

    code_payload = client.post(f"/auth/code/create/{referred['user_id']}").json()
    login = client.post("/auth/code/verify", json={"code": code_payload["code"]}).json()
    token = login["access_token"]

    # top-up for run cost in scaffold
    from backend.store import store

    store.wallets[referred["user_id"]].available_credits = 10

    wallet = client.get("/wallet/me", headers=auth_headers(token)).json()
    assert wallet["run_cost"] == 10

    run = client.post("/runs", json={}, headers=auth_headers(token)).json()
    hold = client.post(
        "/wallet/hold", json={"run_id": run["run_id"]}, headers=auth_headers(token)
    ).json()
    execute = client.post(
        "/runs/execute",
        json={
            "run_id": run["run_id"],
            "hold_id": hold["hold_id"],
            "country": "us",
            "state": "ca",
            "city": "sf",
            "simulate_failure": False,
        },
        headers=auth_headers(token),
    ).json()

    assert execute["status"] == "VERIFIED_SUCCESS"

    ref_wallet = client.post(f"/auth/code/create/{referrer['user_id']}")
    assert ref_wallet.status_code == 200

    assert store.wallets[referrer["user_id"]].available_credits == 8


def test_hold_refunded_on_failure_via_api():
    client = TestClient(app)
    client.post("/testing/reset")

    user = client.post("/users/register", json={"name": "u1"}).json()
    code_payload = client.post(f"/auth/code/create/{user['user_id']}").json()
    login = client.post("/auth/code/verify", json={"code": code_payload["code"]}).json()
    token = login["access_token"]

    from backend.store import store

    store.wallets[user["user_id"]].available_credits = 10

    run = client.post("/runs", json={}, headers=auth_headers(token)).json()
    hold = client.post(
        "/wallet/hold", json={"run_id": run["run_id"]}, headers=auth_headers(token)
    ).json()

    execute = client.post(
        "/runs/execute",
        json={
            "run_id": run["run_id"],
            "hold_id": hold["hold_id"],
            "country": "us",
            "state": "ny",
            "city": "nyc",
            "simulate_failure": True,
        },
        headers=auth_headers(token),
    ).json()

    assert execute["status"] == "FAILED_FINAL"

    wallet = client.get("/wallet/me", headers=auth_headers(token)).json()
    assert wallet["available_credits"] == 10
    assert wallet["locked_credits"] == 0


def test_generated_code_can_be_verified_via_api():
    client = TestClient(app)
    client.post("/testing/reset")

    generated = client.post("/codes/generate")
    assert generated.status_code == 200
    code = generated.json()["code"]
    assert code.startswith("GHS-")
    assert len(code) == 8

    verify_hit = client.get(f"/codes/verify/{code}")
    assert verify_hit.status_code == 200
    assert verify_hit.json() == {"code": code, "exists": True}

    verify_miss = client.get("/codes/verify/GHS-9999")
    assert verify_miss.status_code == 200
    assert verify_miss.json()["exists"] is False
