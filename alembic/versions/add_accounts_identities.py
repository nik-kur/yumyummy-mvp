"""Add accounts, identities and auth_one_time_codes; link users to accounts

Cross-platform identity foundation (Phase 1 of the mobile app).

Safe / non-breaking:
  * Only ADDS tables and columns; never drops or renames existing ones.
  * ``users.telegram_id`` is widened from NOT NULL -> NULL so app-only users
    (Apple/Google/email) can exist without a Telegram id. The UNIQUE index is
    kept, and Postgres permits multiple NULLs, so the bot's invariant holds.
  * Backfills one account + one 'telegram' identity per existing user and sets
    ``users.account_id`` 1:1, so current Telegram users are unchanged.

Revision ID: add_accounts_identities
Revises: add_landing_attribution
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_accounts_identities"
down_revision: Union[str, None] = "add_landing_attribution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- new tables -------------------------------------------------------
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("primary_email", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accounts_id"), "accounts", ["id"], unique=False)
    op.create_index(
        op.f("ix_accounts_primary_email"), "accounts", ["primary_email"], unique=False
    )

    op.create_table(
        "identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_id", name="uq_identity_provider"),
    )
    op.create_index(op.f("ix_identities_id"), "identities", ["id"], unique=False)
    op.create_index(
        op.f("ix_identities_account_id"), "identities", ["account_id"], unique=False
    )

    op.create_table(
        "auth_one_time_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("code_hash", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_one_time_codes_id"), "auth_one_time_codes", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_auth_one_time_codes_purpose"),
        "auth_one_time_codes",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_one_time_codes_code_hash"),
        "auth_one_time_codes",
        ["code_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_one_time_codes_subject"),
        "auth_one_time_codes",
        ["subject"],
        unique=False,
    )

    # --- link users -> accounts ------------------------------------------
    op.add_column("users", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_users_account_id"), "users", ["account_id"], unique=False)
    op.create_foreign_key(
        "fk_users_account_id", "users", "accounts", ["account_id"], ["id"]
    )

    # widen telegram_id so app-only users can exist (UNIQUE index retained)
    op.alter_column("users", "telegram_id", existing_type=sa.String(), nullable=True)

    # --- backfill: 1 account + 1 telegram identity per existing user ------
    # Row-by-row keeps the id mapping simple and correct; this is a one-time
    # migration on an early-stage user base, so the loop cost is irrelevant.
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, telegram_id FROM users")).fetchall()
    for row in users:
        user_id = row[0]
        telegram_id = row[1]
        account_id = conn.execute(
            sa.text(
                "INSERT INTO accounts (created_at) VALUES (CURRENT_TIMESTAMP) RETURNING id"
            )
        ).scalar()
        conn.execute(
            sa.text("UPDATE users SET account_id = :aid WHERE id = :uid"),
            {"aid": account_id, "uid": user_id},
        )
        if telegram_id is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO identities (account_id, provider, provider_id, created_at) "
                    "VALUES (:aid, 'telegram', :tid, CURRENT_TIMESTAMP)"
                ),
                {"aid": account_id, "tid": str(telegram_id)},
            )


def downgrade() -> None:
    op.drop_constraint("fk_users_account_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_account_id"), table_name="users")
    op.drop_column("users", "account_id")
    # NOTE: restoring NOT NULL will fail if any app-only (telegram_id IS NULL)
    # users were created after this migration. Clean those up first if so.
    op.alter_column("users", "telegram_id", existing_type=sa.String(), nullable=False)

    op.drop_index(op.f("ix_auth_one_time_codes_subject"), table_name="auth_one_time_codes")
    op.drop_index(op.f("ix_auth_one_time_codes_code_hash"), table_name="auth_one_time_codes")
    op.drop_index(op.f("ix_auth_one_time_codes_purpose"), table_name="auth_one_time_codes")
    op.drop_index(op.f("ix_auth_one_time_codes_id"), table_name="auth_one_time_codes")
    op.drop_table("auth_one_time_codes")

    op.drop_index(op.f("ix_identities_account_id"), table_name="identities")
    op.drop_index(op.f("ix_identities_id"), table_name="identities")
    op.drop_table("identities")

    op.drop_index(op.f("ix_accounts_primary_email"), table_name="accounts")
    op.drop_index(op.f("ix_accounts_id"), table_name="accounts")
    op.drop_table("accounts")
