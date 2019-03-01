"""Add Image Repost Table

Revision ID: 3cb433829c56
Revises: f18c7b3b626b
Create Date: 2019-02-17 12:21:01.655056

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3cb433829c56'
down_revision = 'f18c7b3b626b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('image_reposts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hamming_distance', sa.Integer(), nullable=True),
    sa.Column('annoy_distance', sa.Float(), nullable=True),
    sa.Column('post_id', sa.String(length=100), nullable=False),
    sa.Column('repost_of', sa.String(length=100), nullable=False),
    sa.Column('detected_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('image_reposts')
    # ### end Alembic commands ###
