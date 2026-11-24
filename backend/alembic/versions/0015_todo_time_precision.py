"""Preserve date precision; expand only, no historical timestamp shifts.

Rollback: retain columns when reverting application. Export date-only data before
any explicit structural downgrade; downgrade refuses to discard such records.
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_todo_time_precision'
down_revision = '0014_todo_location'
branch_labels = None
depends_on = None

CONSTRAINT = "(due_precision = 'datetime' AND due_at IS NOT NULL AND due_date IS NULL) OR (due_precision = 'date' AND due_at IS NULL AND due_date IS NOT NULL) OR (due_precision = 'unknown' AND due_at IS NULL AND due_date IS NULL)"


def upgrade():
    from app.core.config import settings
    op.add_column('todos', sa.Column('due_date', sa.Date(), nullable=True))
    op.add_column('todos', sa.Column('due_precision', sa.String(16), nullable=False, server_default='unknown'))
    op.add_column('todos', sa.Column('due_timezone', sa.String(64), nullable=False, server_default=settings.timezone))
    op.execute("UPDATE todos SET due_precision = 'datetime' WHERE due_at IS NOT NULL")
    # Legacy writers do not know this column. Infer only when they omit it;
    # explicit inconsistent values must still fail the check constraint.
    op.alter_column('todos', 'due_precision', server_default=None)
    op.execute("""CREATE FUNCTION infer_todo_time_precision() RETURNS trigger AS $$
        BEGIN
          IF NEW.due_precision IS NULL THEN
            NEW.due_precision := CASE WHEN NEW.due_at IS NOT NULL THEN 'datetime'
                                     WHEN NEW.due_date IS NOT NULL THEN 'date' ELSE 'unknown' END;
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER infer_todo_time_precision BEFORE INSERT ON todos FOR EACH ROW EXECUTE FUNCTION infer_todo_time_precision()')
    op.create_check_constraint('ck_todos_time_precision', 'todos', CONSTRAINT)


def downgrade():
    if op.get_bind().execute(sa.text('SELECT COUNT(*) FROM todos WHERE due_date IS NOT NULL')).scalar():
        raise RuntimeError('Export and preserve date-only records before structural downgrade')
    op.drop_constraint('ck_todos_time_precision', 'todos', type_='check')
    op.execute('DROP TRIGGER infer_todo_time_precision ON todos')
    op.execute('DROP FUNCTION infer_todo_time_precision()')
    for column in ('due_timezone', 'due_precision', 'due_date'):
        op.drop_column('todos', column)
