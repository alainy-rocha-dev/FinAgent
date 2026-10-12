from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("event_seq", sa.Integer(), nullable=True),
        sa.Column("terminal_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "task_events",
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("payload", sa.String(), nullable=True),
        sa.UniqueConstraint("task_id", name="uq_task_id_task_events"),
    )


def downgrade():
    op.drop_table("task_events")
    op.drop_table("tasks")