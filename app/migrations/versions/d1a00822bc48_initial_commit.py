"""Initial Commit

Revision ID: d1a00822bc48
Revises:
Create Date: 2024-08-24 17:46:30.644010

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a00822bc48"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "usermodel",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("last_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("did_get_shirt", sa.Boolean(), nullable=True),
        sa.Column("did_agree_to_do_kh", sa.Boolean(), nullable=True),
        sa.Column("team_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("availability", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sudo", sa.Boolean(), nullable=True),
        sa.Column("discord_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hackucf_id", sa.Uuid(), nullable=True),
        sa.Column("hackucf_member", sa.Boolean(), nullable=True),
        sa.Column("experience", sa.Integer(), nullable=True),
        sa.Column("waitlist", sa.Integer(), nullable=True),
        sa.Column("team_number", sa.Integer(), nullable=True),
        sa.Column("assigned_run", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("checked_in", sa.Boolean(), nullable=True),
        sa.Column("did_sign_photo_release", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "discordmodel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("mfa", sa.Boolean(), nullable=True),
        sa.Column("avatar", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("banner", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("color", sa.Integer(), nullable=True),
        sa.Column("nitro", sa.Integer(), nullable=True),
        sa.Column("locale", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usermodel.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("discordmodel")
    op.drop_table("usermodel")
    # ### end Alembic commands ###
