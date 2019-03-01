"""post type to repost

Revision ID: f1b37c0e9d53
Revises: da78ebc9b7d0
Create Date: 2019-02-12 20:11:38.554778

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1b37c0e9d53'
down_revision = 'da78ebc9b7d0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reddit_reposts', sa.Column('post_type', sa.String(length=20), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('reddit_reposts', 'post_type')
    # ### end Alembic commands ###
