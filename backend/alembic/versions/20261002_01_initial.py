"""Initial governed domain schema."""
from alembic import op
from app.database import Base
from app.models import *  # noqa: F403
revision="20261002_01"
down_revision=None
branch_labels=None
depends_on=None
def upgrade(): Base.metadata.create_all(bind=op.get_bind())
def downgrade(): Base.metadata.drop_all(bind=op.get_bind())
