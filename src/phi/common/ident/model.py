import sqlalchemy as sa


metadata = sa.MetaData()


users = sa.Table('users', metadata,
                 sa.Column('id', sa.Integer(), nullable=False),
                 sa.Column('name', sa.String(), nullable=False),
                 sa.Column('email_address', sa.String(), nullable=False),
                 sa.PrimaryKeyConstraint('id'),
                 sa.UniqueConstraint('email_address'))


services = sa.Table('services', metadata,
                    sa.Column('user_id', sa.Integer, nullable=False),
                    sa.Column('sv_id', sa.String, nullable=False),
                    sa.Column(
                        'sv_name',
                        sa.Enum('fb', 'gh', name='svc_type'),
                        nullable=False
                    ),

                    sa.UniqueConstraint('sv_id', 'sv_name'),
                    sa.PrimaryKeyConstraint('sv_name', 'user_id'),
                    sa.ForeignKeyConstraint(['user_id'], ['users.id']))
