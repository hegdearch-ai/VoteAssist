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

from app.db import Member, SessionLocal, init_db  # noqa: E402
from app.services.members import mask_email, norm_email, norm_phone  # noqa: E402

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

    init_db()
    db = SessionLocal()
    seen, added, updated, skipped, no_email, no_phone = set(), 0, 0, 0, 0, 0
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
        data = dict(sr_no=int(sr) if isinstance(sr, (int, float)) else None, name=name,
                    email_norm=email, phone_e164=phone, email_masked=mask_email(email),
                    city=(str(get(row, "city")).strip() if get(row, "city") else None))
        existing = db.get(Member, mid)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Member(member_id=mid, **data))
            added += 1
    db.commit()
    print(f"added={added} updated={updated} skipped={skipped} "
          f"without_email={no_email} without_valid_mobile={no_phone}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
