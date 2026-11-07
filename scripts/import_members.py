"""Import the membership Excel once.

Usage (from a laptop; never commit or upload the file):
    DATABASE_URL=<railway public postgres url> python scripts/import_members.py members.xlsx
    # or:  railway run python scripts/import_members.py members.xlsx

Expected headers (case/spacing tolerant):
    Sr No | Member Name | Membership No | Email ID | Mobile No | City
Re-running is safe: rows are upserted by Membership No.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # noqa: E402

from app.db import Member, engine, init_db  # noqa: E402
from app.services.members import mask_email, norm_email, norm_phone  # noqa: E402

BATCH = 500

ALIASES = {
    "sr_no": ["srno", "sno", "slno", "serialno"],
    "name": ["membername", "name"],
    "member_id": ["membershipno", "membershipnumber", "memberid", "membershipid"],
    "email": ["emailid", "email", "emailaddress"],
    "phone": ["mobileno", "mobile", "phone", "mobilenumber", "contactno"],
    "city": ["city"],
}


def key(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def main(path: str) -> None:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = ws.iter_rows(values_only=True)
    headers = [key(h) for h in next(rows)]
    col = {}
    for field, names in ALIASES.items():
        for i, h in enumerate(headers):
            if h in names:
                col[field] = i
                break
    missing = [f for f in ("name", "member_id") if f not in col]
    if missing:
        sys.exit(f"Could not find columns for: {missing}. Headers seen: {headers}")

    def get(row, f):
        return row[col[f]] if f in col and col[f] < len(row) else None

    records, seen, skipped, no_email, no_phone = [], set(), 0, 0, 0
    for row in rows:
        mid = str(get(row, "member_id") or "").strip()
        if mid.endswith(".0"):
            mid = mid[:-2]
        name = str(get(row, "name") or "").strip()
        if not mid or not name or mid in seen:
            skipped += 1
            continue
        seen.add(mid)
        email, phone = norm_email(get(row, "email")), norm_phone(get(row, "phone"))
        no_email += email is None
        no_phone += phone is None
        sr = get(row, "sr_no")
        records.append(dict(member_id=mid, sr_no=int(sr) if isinstance(sr, (int, float)) else None,
                            name=name, email_norm=email, phone_e164=phone,
                            email_masked=mask_email(email),
                            city=(str(get(row, "city")).strip() if get(row, "city") else None)))
    print(f"read {len(records)} members from Excel; uploading in batches of {BATCH}...")

    init_db()
    insert = pg_insert if engine.dialect.name == "postgresql" else sqlite_insert
    with engine.connect() as conn:
        existing = set(conn.execute(select(Member.member_id)).scalars())
    for i in range(0, len(records), BATCH):
        chunk = records[i:i + BATCH]
        stmt = insert(Member).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[Member.member_id],
            set_={c: stmt.excluded[c] for c in chunk[0] if c != "member_id"})
        with engine.begin() as conn:   # one short transaction per batch
            conn.execute(stmt)
        print(f"  uploaded {min(i + BATCH, len(records))}/{len(records)}")
    added = sum(r["member_id"] not in existing for r in records)
    print(f"added={added} updated={len(records) - added} skipped={skipped} "
          f"without_email={no_email} without_valid_mobile={no_phone}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
