from pathlib import Path

from eburon_crm import EburonCRM


class TestEburonCRM:
    def test_imports_contacts_from_csv_and_preserves_unknown_columns(
        self, tmp_path: Path
    ):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        csv_data = (
            "name,phone,email,company,status,plan\n"
            "Ada Lovelace,+14155550100,ada@example.com,Analytical,new,Pro\n"
            "Grace Hopper,+14155550101,grace@example.com,Navy,follow_up,Enterprise\n"
        ).encode()

        result = crm.import_contacts_csv(csv_data, "contacts.csv")

        assert result["imported_count"] == 2
        assert result["skipped_count"] == 0
        contacts = crm.list_contacts()
        assert [contact["name"] for contact in contacts] == [
            "Ada Lovelace",
            "Grace Hopper",
        ]
        assert contacts[0]["metadata"] == {"plan": "Pro"}
        assert contacts[1]["status"] == "follow_up"

    def test_import_reports_invalid_rows_without_crashing(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        csv_data = (
            "name,phone,email\n"
            "Missing Phone,,missing@example.com\n"
            "Valid Contact,+14155550102,valid@example.com\n"
        ).encode()

        result = crm.import_contacts_csv(csv_data, "mixed.csv")

        assert result["imported_count"] == 1
        assert result["skipped_count"] == 1
        assert result["invalid_rows"] == [
            {"row": 2, "reason": "missing phone number"}
        ]
        assert crm.list_contacts()[0]["name"] == "Valid Contact"

    def test_persists_contacts_across_instances(self, tmp_path: Path):
        db_path = tmp_path / "crm.sqlite3"
        EburonCRM(db_path).import_contacts_csv(
            b"name,phone\n" b"Linus Torvalds,+14155550103\n",
            "one.csv",
        )

        contacts = EburonCRM(db_path).list_contacts()

        assert len(contacts) == 1
        assert contacts[0]["phone"] == "+14155550103"

    def test_records_calls_and_dashboard_stats(self, tmp_path: Path):
        crm = EburonCRM(tmp_path / "crm.sqlite3")
        contact = crm.import_contacts_csv(
            b"name,phone,status\n" b"Follow Up,+14155550104,follow_up\n",
            "contacts.csv",
        )["contacts"][0]

        crm.create_call_record(
            call_id="call-1",
            direction="outbound",
            from_number="+14155550000",
            to_number=contact["phone"],
            status="queued",
            contact_id=contact["id"],
        )
        crm.update_call_status("call-1", "completed", ended=True, outcome="resolved")

        calls = crm.list_calls()
        stats = crm.dashboard_stats(active_calls=3)

        assert calls[0]["call_id"] == "call-1"
        assert calls[0]["duration_seconds"] is not None
        assert stats == {
            "active_calls": 3,
            "calls_today": 1,
            "follow_ups": 1,
            "total_contacts": 1,
        }
