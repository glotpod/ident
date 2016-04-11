import sqlalchemy as sa
import sqlalchemy_utils as sau

from glotpod.ident import cfg


metadata = sa.MetaData()


users = sa.Table('users', metadata,
                 sa.Column('id', sa.Integer(), nullable=False),
                 sa.Column('name', sa.String(), nullable=False),
                 sa.Column('picture_url', sa.String(), nullable=True),
                 sa.Column('email_address', sa.String(), nullable=True),
                 sa.PrimaryKeyConstraint('id'),
                 sa.UniqueConstraint('email_address'))


secret_key = cfg.get('database.model.github.secret_key')
github_info = sa.Table('github_info', metadata,
                       sa.Column('id', sa.Integer(), nullable=False),
                       sa.Column('login', sa.String(), nullable=False),
                       sa.Column('access_token',
                                 sau.EncryptedType(sa.String, secret_key),
                                 nullable=False),
                       sa.Column('user_id', sa.Integer(), nullable=False),
                       sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
                       sa.PrimaryKeyConstraint('id'),
                       sa.UniqueConstraint('access_token'),
                       sa.UniqueConstraint('login'),
                       sa.UniqueConstraint('user_id'))
