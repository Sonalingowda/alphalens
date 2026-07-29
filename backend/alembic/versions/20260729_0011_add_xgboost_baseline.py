"""Allow immutable XGBoost regression experiments."""

from collections.abc import Sequence

from alembic import op


revision: str = "20260729_0011"
down_revision: str | None = "20260729_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_regression_experiments_model_family",
        "regression_experiments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_regression_experiments_model_family",
        "regression_experiments",
        (
            "model_family IN "
            "('linear_regression', 'ridge_regression', "
            "'random_forest_regression', 'xgboost_regression')"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_regression_experiments_model_family",
        "regression_experiments",
        type_="check",
    )
    op.create_check_constraint(
        "ck_regression_experiments_model_family",
        "regression_experiments",
        (
            "model_family IN "
            "('linear_regression', 'ridge_regression', "
            "'random_forest_regression')"
        ),
    )
