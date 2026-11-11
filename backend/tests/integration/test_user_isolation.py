"""Cross-account isolation tests for the HTTP surface.

Auth is disabled in the suite, so the owner dependency is overridden to
simulate two signed-in Auth0 subjects. Every route must behave as if the
other account's ids do not exist: 404, never data or a 403 that confirms
existence.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import auth0_setup
import api.routes.memory as memory_routes
from api.routes.analyze import _RUNS
from api.routes.upload import _UPLOADED_FILES
from main import app
from models.schemas import Memory, MemoryType
from services.memory_store import MemoryStore

USER_A = "auth0|user-a"
USER_B = "auth0|user-b"


@pytest.fixture()
def as_user():
    def _switch(user_id: str) -> TestClient:
        app.dependency_overrides[auth0_setup.get_current_user_id] = lambda: user_id
        # The routers are also gated by require_session when a tenant is
        # configured; override it too so these tests don't depend on .env.
        app.dependency_overrides[auth0_setup.require_session] = lambda: {
            "user": {"sub": user_id}
        }
        return TestClient(app)

    yield _switch
    app.dependency_overrides.pop(auth0_setup.get_current_user_id, None)
    app.dependency_overrides.pop(auth0_setup.require_session, None)


@pytest.fixture(autouse=True)
def clean_registries():
    _UPLOADED_FILES.clear()
    _RUNS.clear()
    yield
    _UPLOADED_FILES.clear()
    _RUNS.clear()


@pytest.fixture()
def memory_store(tmp_path, monkeypatch):
    store = MemoryStore(tmp_path / "isolation.db")
    monkeypatch.setattr(memory_routes, "_store", store)
    return store


def _memory(memory_id: str = "mem_isolation") -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        memory_id=memory_id,
        company_id="acme",
        memory_type=MemoryType.BUSINESS_PATTERN,
        content="Enterprise renewals spike at quarter end.",
        created_at=now,
        last_reinforced_at=now,
    )


def test_memory_is_invisible_and_immutable_to_another_user(as_user, memory_store):
    memory_store.create(_memory(), user_id=USER_A)

    assert as_user(USER_B).get("/api/memory", params={"company_id": "acme"}).json() == []
    assert as_user(USER_B).patch(
        f"/api/memory/{memory_store.list_for_company('acme', user_id=USER_A)[0].memory_id}",
        json={"content": "hijacked"},
    ).status_code == 404
    assert as_user(USER_B).delete(
        f"/api/memory/{memory_store.list_for_company('acme', user_id=USER_A)[0].memory_id}"
    ).status_code == 404

    assert len(memory_store.list_for_company("acme", user_id=USER_A)) == 1


def test_upload_belongs_only_to_its_uploader(as_user):
    csv = b"date,account,account_type,amount\n2026-08-01,Sales,revenue,1200\n"
    uploaded = as_user(USER_A).post(
        "/api/upload",
        files={"file": ("transactions.csv", csv, "text/csv")},
        data={"company_id": "acme"},
    )
    assert uploaded.status_code == 200, uploaded.text
    file_id = uploaded.json()["file_id"]

    assert as_user(USER_B).get(f"/api/uploads/{file_id}").status_code == 404
    assert as_user(USER_B).post(f"/api/uploads/{file_id}/confirm", json={"use_as": "transaction_csv"}).status_code == 404
    assert as_user(USER_B).post(
        "/api/analyze",
        json={"company_id": "acme", "transaction_file_ids": [file_id]},
    ).status_code == 404

    assert as_user(USER_A).get(f"/api/uploads/{file_id}").status_code == 200


def test_runs_reports_and_scenarios_are_scoped_to_the_owner(as_user):
    _RUNS["run_owned_by_a"] = {
        "status": "complete",
        "state": {"company_id": "acme", "current_period": "2026-08"},
        "error": None,
        "user_id": USER_A,
    }

    listing = as_user(USER_B).get("/api/runs")
    assert listing.status_code == 200
    assert listing.json() == []

    assert as_user(USER_B).get("/api/runs/run_owned_by_a").status_code == 404
    assert as_user(USER_B).get("/api/runs/run_owned_by_a/evidence").status_code == 404
    assert as_user(USER_B).get("/api/runs/run_owned_by_a/trace").status_code == 404
    assert as_user(USER_B).get("/api/reports/run_owned_by_a/markdown").status_code == 404
    assert as_user(USER_B).get("/api/reports/run_owned_by_a/powerbi").status_code == 404
    assert as_user(USER_B).post(
        "/api/scenarios/simulate", json={"run_id": "run_owned_by_a", "exclude_drivers": []}
    ).status_code == 404
    assert as_user(USER_B).post(
        "/api/stress-tests/run", json={"run_id": "run_owned_by_a"}
    ).status_code == 404

    # The owner still sees the run in their own listing.
    assert [r["run_id"] for r in as_user(USER_A).get("/api/runs").json()] == ["run_owned_by_a"]


def test_memory_store_rejects_cross_user_reads_and_writes(tmp_path):
    store = MemoryStore(tmp_path / "store.db")
    memory = _memory("mem_direct")
    store.create(memory, user_id=USER_A)

    assert store.get("mem_direct", user_id=USER_B) is None
    assert store.list_for_company("acme", user_id=USER_B) == []
    store.delete("mem_direct", user_id=USER_B)
    assert store.get("mem_direct", user_id=USER_A) is not None

    with pytest.raises(KeyError):
        store.user_correct("mem_direct", "hijacked", user_id=USER_B)
