from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from eburon_crm import EburonCRM
from eburon_support_app import OutboundCallJob, create_app


class FakeOutboundStarter:
    def __init__(self):
        self.jobs: list[OutboundCallJob] = []

    async def __call__(self, job: OutboundCallJob) -> None:
        self.jobs.append(job)


class TestEburonSupportApp:
    def test_upload_contacts_and_returns_dashboard_stats(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        app = create_app(crm=crm, outbound_starter=FakeOutboundStarter())
        client = TestClient(app)

        response = client.post(
            "/api/contacts/upload",
            files={
                "file": (
                    "contacts.csv",
                    b"name,phone,status\nAda,+14155550100,follow_up\n",
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        assert response.json()["imported_count"] == 1
        contacts = client.get("/api/contacts").json()
        stats = client.get("/api/dashboard/stats").json()
        assert contacts[0]["name"] == "Ada"
        assert stats["total_contacts"] == 1
        assert stats["follow_ups"] == 1

    def test_outbound_call_uses_selected_contact_phone(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        contact = crm.import_contacts_csv(
            b"name,phone\nAda,+14155550100\n",
            "contacts.csv",
        )["contacts"][0]
        starter = FakeOutboundStarter()
        app = create_app(crm=crm, outbound_starter=starter)
        client = TestClient(app)

        response = client.post(
            "/api/outbound-call",
            json={
                "contact_id": contact["id"],
                "from_number": "+14155550000",
                "goal": "Check whether Ada needs help with Eburon AI onboarding.",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "queued"
        assert starter.jobs[0].to_number == "+14155550100"
        assert starter.jobs[0].contact_id == contact["id"]
        assert starter.jobs[0].goal.startswith("Check whether Ada")
        assert crm.list_calls()[0]["call_id"] == payload["call_id"]

    def test_outbound_call_rejects_request_without_target(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        app = create_app(crm=crm, outbound_starter=FakeOutboundStarter())
        client = TestClient(app)

        response = client.post(
            "/api/outbound-call",
            json={"from_number": "+14155550000"},
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Provide either contact_id or to_number for outbound calls."
        }

    def test_active_calls_are_serialized_from_registry(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        app = create_app(crm=crm, outbound_starter=FakeOutboundStarter())
        app.state.call_registry.create("call-1")
        client = TestClient(app)

        response = client.get("/api/calls/active")

        assert response.status_code == 200
        assert response.json()[0]["call_id"] == "call-1"
        assert response.json()[0]["status"] == "active"
