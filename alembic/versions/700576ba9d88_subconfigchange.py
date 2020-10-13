"""subconfigchange

Revision ID: 700576ba9d88
Revises: a4829f4a5121
Create Date: 2020-10-10 13:33:35.001655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '700576ba9d88'
down_revision = 'a4829f4a5121'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('subreddit', table_name='reddit_monitored_sub_config_change')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index('subreddit', 'reddit_monitored_sub_config_change', ['subreddit'], unique=True)
    # ### end Alembic commands ###
