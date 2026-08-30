from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.CheckConstraint("code ~ '^[A-Z]{3,8}$'", name="ck_currencies_code_format"),
        sa.PrimaryKeyConstraint("code", name="pk_currencies"),
    )
    op.create_table(
        "exchange_rates",
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("usd_rate", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.CheckConstraint("usd_rate > 0", name="ck_exchange_rates_positive"),
        sa.ForeignKeyConstraint(
            ("currency_code",),
            ("currencies.code",),
            name="fk_exchange_rates_currency",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("currency_code", "rate_date", name="pk_exchange_rates"),
    )
    op.create_table(
        "account_balances",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("balance_usd", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.CheckConstraint("account_id BETWEEN 100 AND 999", name="ck_account_balances_id_range"),
        sa.CheckConstraint(
            "char_length(btrim(name)) > 0", name="ck_account_balances_name_nonempty"
        ),
        sa.PrimaryKeyConstraint("account_id", name="pk_account_balances"),
    )


def downgrade() -> None:
    op.drop_table("account_balances")
    op.drop_table("exchange_rates")
    op.drop_table("currencies")
