"""
Backfill user emails onto existing Adapty profiles (Adapty Mail audience).

Usage:
    python scripts/adapty_backfill_emails.py            # dry run, prints the plan
    python scripts/adapty_backfill_emails.py --apply    # actually writes

Everyone who signs in gets their email pushed to Adapty from `/app/billing/sync`
(and, from 1.0.5 on, by the app itself). Neither reaches the people a win-back
campaign is aimed at: someone who abandoned the paywall in July will not open
the app again, so their profile stays without an email and Adapty Mail can't
address them. This walks the accounts table once and closes that gap.

Reads ADAPTY_SERVER_API_KEY and DATABASE_URL from the environment / .env, so it
talks to whichever database the app itself is configured against.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.service import resolve_account_email  # noqa: E402
from app.billing.adapty_profile import push_profile_attributes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.account import Account  # noqa: E402

# Adapty allows a couple of requests per second; stay comfortably under it.
REQUEST_INTERVAL_S = 0.4


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write to Adapty (default: dry run)")
    parser.add_argument("--limit", type=int, default=0, help="stop after N accounts (0 = all)")
    args = parser.parse_args()

    if args.apply and not settings.adapty_server_api_key:
        print("ADAPTY_SERVER_API_KEY is not set — nothing would be written.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        accounts = db.query(Account).order_by(Account.id.asc()).all()
        targets = []
        for account in accounts:
            email = resolve_account_email(db, account)
            if email:
                targets.append((account, email))

        if args.limit:
            targets = targets[: args.limit]

        print(f"{len(accounts)} accounts, {len(targets)} with an email on file")
        if not args.apply:
            for account, email in targets:
                print(f"  would push account={account.id} email={email}")
            print("\nDry run. Re-run with --apply to write.")
            return 0

        ok = 0
        for account, email in targets:
            if push_profile_attributes(
                account.id, email=email, display_name=account.display_name
            ):
                ok += 1
            time.sleep(REQUEST_INTERVAL_S)

        # Misses are expected and harmless: accounts that never reached Adapty
        # (Telegram-only, or an install that never opened the paywall) have no
        # profile to patch.
        print(f"pushed {ok}/{len(targets)}; {len(targets) - ok} had no Adapty profile")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
