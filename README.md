# FamilyKitty

A mobile-first family savings and loan ledger. It does not connect to banks or move money.

## Run locally
1. Python 3.10+
2. `python -m venv .venv`
3. Activate the environment
4. `pip install -r requirements.txt`
5. `python app.py`
6. Open http://127.0.0.1:5000

The SQLite database and demo seed data are created automatically on first run. Demo group: **Bhushan Family**.

## Included in this starter
- Responsive dashboard and mobile navigation
- Member list and tracked-only member creation
- Admin-recorded deposits with payment mode, date and note
- Loan disbursement constrained by available pool
- Flexible repayments with interest-first allocation
- Transaction CSV export
- Basic group settings and audit log
- Installable PWA shell and offline caching of the app shell

## Important production gaps
This is a runnable MVP starter, not a production financial system. Phone OTP authentication, multi-group membership, granular role enforcement, proof uploads, monthly due generation, partial/advance reconciliation, interest and penalty accrual jobs, WhatsApp provider integration, PDF export, month locking, withdrawal approvals, comments/disputes, encryption/key management, backup/restore, localization and robust offline synchronization still need implementation and testing. The current demo admin identity is illustrative and is not secure authentication.

Before production: use PostgreSQL, migrations, server-side authorization, a real OTP provider, object storage for receipts, a queue/scheduler, idempotency keys, immutable append-only ledger events, automated reconciliation and comprehensive financial tests. Configure secrets through environment variables; never deploy with the development secret key.

## Assumptions
- All monetary values are stored as integer paise? No: this starter stores whole INR rupees to keep the demo simple. Production should store paise as integers.
- Demo data seeds May–October 2026 and a ₹10,000 active loan for Vaibhav.
- The current month contribution display uses actual due rows; a production scheduler must create each month's due rows from effective-dated contribution history.
- The UI is English-first and uses Indian-style comma formatting.
