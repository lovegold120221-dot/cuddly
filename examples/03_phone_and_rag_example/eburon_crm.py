import csv
import io
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional


HEADER_ALIASES = {
    "name": {"name", "full_name", "fullname", "contact_name"},
    "phone": {"phone", "phone_number", "phonenumber", "mobile", "number"},
    "email": {"email", "email_address", "emailaddress"},
    "company": {"company", "organization", "organisation", "account"},
    "status": {"status", "lead_status", "leadstatus"},
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def _canonical_header(header: str) -> Optional[str]:
    normalized = _normalize_header(header)
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def _normalize_phone(phone: str) -> Optional[str]:
    value = phone.strip()
    if not value:
        return None

    normalized = (
        value.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace(".", "")
    )
    digits = [char for char in normalized if char.isdigit()]
    if len(digits) < 7:
        return None
    return normalized


def _row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return dict(row)


class EburonCRM:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    imported_rows INTEGER NOT NULL DEFAULT 0,
                    skipped_rows INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    email TEXT,
                    company TEXT,
                    status TEXT NOT NULL DEFAULT 'new',
                    source_upload_id INTEGER,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(source_upload_id) REFERENCES uploads(id)
                );

                CREATE TABLE IF NOT EXISTS calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    call_id TEXT NOT NULL UNIQUE,
                    contact_id INTEGER,
                    direction TEXT NOT NULL,
                    from_number TEXT NOT NULL,
                    to_number TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    outcome TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    FOREIGN KEY(contact_id) REFERENCES contacts(id)
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_id INTEGER,
                    call_id TEXT,
                    note_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(contact_id) REFERENCES contacts(id)
                );
                """
            )

    def import_contacts_csv(
        self, content: bytes, filename: str
    ) -> dict[str, object]:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        imported_count = 0
        invalid_rows: list[dict[str, object]] = []
        imported_contacts: list[dict[str, object]] = []
        created_at = _now()

        with self._connect() as connection:
            upload_id = connection.execute(
                """
                INSERT INTO uploads (filename, imported_rows, skipped_rows, created_at)
                VALUES (?, 0, 0, ?)
                """,
                (filename, created_at),
            ).lastrowid

            for row_number, row in enumerate(reader, start=2):
                contact = self._parse_contact_row(row)
                phone = contact.get("phone")
                if not phone:
                    invalid_rows.append(
                        {"row": row_number, "reason": "missing phone number"}
                    )
                    continue

                contact_id = self._upsert_contact(connection, contact, upload_id)
                imported_contacts.append(self.get_contact(contact_id, connection))
                imported_count += 1

            skipped_count = len(invalid_rows)
            connection.execute(
                """
                UPDATE uploads
                SET imported_rows = ?, skipped_rows = ?
                WHERE id = ?
                """,
                (imported_count, skipped_count, upload_id),
            )

        return {
            "upload_id": upload_id,
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "invalid_rows": invalid_rows,
            "contacts": imported_contacts,
        }

    def _parse_contact_row(self, row: dict[str, str]) -> dict[str, object]:
        values: dict[str, str] = {
            "name": "",
            "phone": "",
            "email": "",
            "company": "",
            "status": "new",
        }
        metadata: dict[str, str] = {}

        for header, raw_value in row.items():
            value = (raw_value or "").strip()
            canonical = _canonical_header(header)
            if canonical is None:
                if value:
                    metadata[header] = value
                continue
            if value:
                values[canonical] = value

        phone = _normalize_phone(values["phone"])
        name = values["name"] or phone or "Unknown caller"

        return {
            "name": name,
            "phone": phone,
            "email": values["email"] or None,
            "company": values["company"] or None,
            "status": values["status"] or "new",
            "metadata": metadata,
        }

    def _upsert_contact(
        self,
        connection: sqlite3.Connection,
        contact: dict[str, object],
        upload_id: int,
    ) -> int:
        timestamp = _now()
        metadata_json = json.dumps(contact["metadata"], sort_keys=True)
        connection.execute(
            """
            INSERT INTO contacts (
                name, phone, email, company, status, source_upload_id,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                company = excluded.company,
                status = excluded.status,
                source_upload_id = excluded.source_upload_id,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                contact["name"],
                contact["phone"],
                contact["email"],
                contact["company"],
                contact["status"],
                upload_id,
                metadata_json,
                timestamp,
                timestamp,
            ),
        )
        row = connection.execute(
            "SELECT id FROM contacts WHERE phone = ?", (contact["phone"],)
        ).fetchone()
        return int(row["id"])

    def get_contact(
        self, contact_id: int, connection: Optional[sqlite3.Connection] = None
    ) -> dict[str, object]:
        owns_connection = connection is None
        active_connection = connection or self._connect()
        try:
            row = active_connection.execute(
                "SELECT * FROM contacts WHERE id = ?", (contact_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown contact_id: {contact_id}")
            return self._serialize_contact(row)
        finally:
            if owns_connection:
                active_connection.close()

    def list_contacts(self, search: Optional[str] = None) -> list[dict[str, object]]:
        with self._connect() as connection:
            if search:
                pattern = f"%{search}%"
                rows = connection.execute(
                    """
                    SELECT * FROM contacts
                    WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? OR company LIKE ?
                    ORDER BY id ASC
                    """,
                    (pattern, pattern, pattern, pattern),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM contacts ORDER BY id ASC"
                ).fetchall()
        return [self._serialize_contact(row) for row in rows]

    def _serialize_contact(self, row: sqlite3.Row) -> dict[str, object]:
        contact = _row_to_dict(row)
        contact["metadata"] = json.loads(str(contact.pop("metadata_json")))
        return contact

    def create_call_record(
        self,
        call_id: str,
        direction: str,
        from_number: str,
        to_number: str,
        status: str,
        contact_id: Optional[int] = None,
        summary: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> dict[str, object]:
        started_at = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO calls (
                    call_id, contact_id, direction, from_number, to_number,
                    status, summary, outcome, started_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(call_id) DO UPDATE SET
                    contact_id = excluded.contact_id,
                    direction = excluded.direction,
                    from_number = excluded.from_number,
                    to_number = excluded.to_number,
                    status = excluded.status,
                    summary = excluded.summary,
                    outcome = excluded.outcome
                """,
                (
                    call_id,
                    contact_id,
                    direction,
                    from_number,
                    to_number,
                    status,
                    summary,
                    outcome,
                    started_at,
                ),
            )
        return self.get_call(call_id)

    def update_call_status(
        self,
        call_id: str,
        status: str,
        ended: bool = False,
        summary: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> dict[str, object]:
        ended_at = _now() if ended else None
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM calls WHERE call_id = ?", (call_id,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"Unknown call_id: {call_id}")

            connection.execute(
                """
                UPDATE calls
                SET status = ?,
                    ended_at = COALESCE(?, ended_at),
                    summary = COALESCE(?, summary),
                    outcome = COALESCE(?, outcome)
                WHERE call_id = ?
                """,
                (status, ended_at, summary, outcome, call_id),
            )
        return self.get_call(call_id)

    def get_call(self, call_id: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT calls.*, contacts.name AS contact_name
                FROM calls
                LEFT JOIN contacts ON contacts.id = calls.contact_id
                WHERE call_id = ?
                """,
                (call_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown call_id: {call_id}")
        return self._serialize_call(row)

    def list_calls(self, limit: int = 50) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT calls.*, contacts.name AS contact_name
                FROM calls
                LEFT JOIN contacts ON contacts.id = calls.contact_id
                ORDER BY calls.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._serialize_call(row) for row in rows]

    def create_note(
        self,
        note_text: str,
        contact_id: Optional[int] = None,
        call_id: Optional[str] = None,
    ) -> dict[str, object]:
        timestamp = _now()
        with self._connect() as connection:
            note_id = connection.execute(
                """
                INSERT INTO notes (contact_id, call_id, note_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (contact_id, call_id, note_text, timestamp),
            ).lastrowid
            row = connection.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
        return _row_to_dict(row)

    def dashboard_stats(self, active_calls: int = 0) -> dict[str, int]:
        today = _now().split("T", maxsplit=1)[0]
        with self._connect() as connection:
            total_contacts = connection.execute(
                "SELECT COUNT(*) AS count FROM contacts"
            ).fetchone()["count"]
            calls_today = connection.execute(
                """
                SELECT COUNT(*) AS count FROM calls
                WHERE started_at LIKE ?
                """,
                (f"{today}%",),
            ).fetchone()["count"]
            follow_ups = connection.execute(
                """
                SELECT COUNT(*) AS count FROM contacts
                WHERE status = 'follow_up'
                """
            ).fetchone()["count"]

        return {
            "active_calls": active_calls,
            "calls_today": int(calls_today),
            "follow_ups": int(follow_ups),
            "total_contacts": int(total_contacts),
        }

    def _serialize_call(self, row: sqlite3.Row) -> dict[str, object]:
        call = _row_to_dict(row)
        started_at = datetime.fromisoformat(str(call["started_at"]))
        ended_at_value = call.get("ended_at")
        call["duration_seconds"] = None
        if ended_at_value:
            ended_at = datetime.fromisoformat(str(ended_at_value))
            call["duration_seconds"] = (ended_at - started_at).total_seconds()
        return call
