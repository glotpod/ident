import json

import jsonpatch

from collections.abc import Mapping
from functools import reduce

from aiohttp import web
from psycopg2 import DataError, IntegrityError, errorcodes
from sqlalchemy.sql import select
from voluptuous import All, Any, Schema, Required, Remove, Length, MultipleInvalid

from phi.common.ident.model import users, services

__all__ = ['create_user', 'get_user', 'patch_user', 'HandlerError']


user_schema = Schema({
    Remove('id'): int,
    Required('name'): All(str, str.strip, Length(min=1)),
    Required('email'): All(str, str.strip, Length(min=1)),
    'services': {
        Any('github', 'facebook'): {
            Required('id'): All(str, str.strip, Length(min=1))
        }
    },
})


async def get_user(request):
    user_id = request.match_info['user_id']

    try:
        user_id = int(user_id)
    except:
        raise web.HTTPNotFound

    async with request['db_pool'].acquire() as conn:
        user_data = {}
        query = select([users, services]).where(users.c.id == user_id)
        query = query.where(users.c.id == services.c.user_id)

        async for row in conn.execute(query):
            user_data['id'] = row['id']
            user_data['name'] = row['name']
            user_data['email'] = row['email_address']
            user_data.setdefault('services', {})

            if row['sv_id'] is not None:
                data = {'id': row['sv_id']}
                key = 'facebook' if row['sv_name'] == 'fb' else 'github'
                user_data['services'][key] = data

        if not user_data:
            raise web.HTTPNotFound

        return web.json_response(user_data)


async def __OLD_get_user(helpers, *, user_id=None, email=None,
                   github_id=None, facebook_id=None):
    conn = helpers['db_conn']
    decrypt = helpers['db_fernet'].decrypt

    searches = []

    if user_id is not None:
        searches.append(users.c.id == user_id)

    if github_id is not None:
        searches.append(
            (services.c.sv_id == github_id) &
            (services.c.sv_name == 'gh')
        )

    if facebook_id is not None:
        searches.append(
            (services.c.sv_id == facebook_id) &
            (services.c.sv_name == 'fb')
        )

    if email is not None:
        searches.append(users.c.email_address == email)

    qry = select(
        [users, services],
        for_update=helpers.get('lock_rows', False)  # patch_user may ask it
    ).where(
        reduce(lambda a, b: a & b, searches)
    ).where(users.c.id == services.c.user_id)

    user_data = {}

    try:
        async for row in conn.execute(qry):
            user_data['id'] = row['id']
            user_data['name'] = row['name']
            user_data['email'] = row['email_address']

            if row['picture_url'] is not None:
                user_data['picture_url'] = row['picture_url']

            if row['sv_id'] is not None:
                data = {
                    'id': row['sv_id'],
                    'access_token': decrypt(
                        row['access_token'].tobytes()
                    ).decode('utf-8')
                }
                key = 'facebook' if row['sv_name'] == 'fb' else 'github'
                user_data[key] = data

    except DataError:
        pass

    if not user_data:
        raise HandlerError('not_found')
    else:
        return user_data


async def create_user(request):
    try:
        # Make sure the incoming data is in a valid format
        # if request.content_type == "application/x-www-form-urlencoded":
        #     data = user_schema(await request.post())

        # else:
        #     data = user_schema(await request.json())

        # fixme: no standard on nested data structures with urlencoded
        data = user_schema(await request.json())

        # Get a database connection from the pool
        async with request['db_pool'].acquire() as conn:
            # Create a transaction for the insertion queries; this
            # is an all or nothing deal
            async with conn.begin() as transaction:
                # Construct the insert query to create the user object
                query = users.insert().values(
                    name=data['name'],
                    email_address=data['email']
                )
                user_id = await conn.scalar(query.returning(users.c.id))

                data.setdefault('services', {})

                if 'facebook' in data['services']:
                    await conn.execute(
                        services.insert().values(
                            user_id=user_id,
                            sv_name='fb',
                            sv_id=data['services']['facebook']['id']
                        )
                    )

                if 'github' in data['services']:
                    await conn.execute(
                        services.insert().values(
                            user_id=user_id,
                            sv_name='gh',
                            sv_id=data['services']['github']['id']
                        )
                    )

    except MultipleInvalid:
        raise web.HTTPBadRequest

    except IntegrityError as e:
        if e.pgcode == errorcodes.UNIQUE_VIOLATION:
            print(e)
            raise web.HTTPConflict
        else:
            raise

    else:
        # Construct the
        data['id'] = user_id

        # # Send a notification about the creation of this user
        # await helpers['notify'](json.dumps(data).encode('utf-8'))

        # Construct a URL to the resource
        user_url = request.app.router.named_resources()['user'].url(
            parts={'user_id': user_id}
        )

        # ... and headers
        headers = {'Location': user_url}

        return web.json_response({'id': user_id}, status=201, headers=headers)


async def patch_user(helpers, user_id, ops):
    conn = helpers['db_conn']
    encrypt = helpers['db_fernet'].encrypt

    # Get the user info to patch, while locking the relating database rows
    # for the remainder of the transaction.
    helpers['lock_rows'] = True
    user_data = await get_user(helpers, user_id=user_id)

    # Patch the user data
    try:
        patched_data = user_schema(jsonpatch.apply_patch(user_data, ops))
    except (TypeError, ValueError, jsonpatch.InvalidJsonPatch,
            jsonpatch.JsonPointerException):
        raise ValueError(ops)
    except MultipleInvalid:
        raise HandlerError('invalid_patch_result')
    except:
        raise HandlerError('patch_failed')
    else:
        # Write the patched data back into the database
        try:
            # Starting with the users table
            qry = users.update().where(users.c.id == user_id).values(
                name=patched_data['name'],
                email_address=patched_data['email'],
                picture_url=patched_data.get('picture_url'))
            await conn.execute(qry)

            # The updates to the services table
            for key, svc_name in (('facebook', 'fb'), ('github', 'gh')):
                matched_record = (
                    (services.c.user_id == user_id) &
                    (services.c.sv_name == svc_name)
                )

                if key not in patched_data and key in user_data:
                    # if the service was there before, it has to be
                    # removed
                    qry = services.delete(matched_record)
                    await conn.execute(qry)

                elif key in patched_data:
                    args = {
                        'sv_id': patched_data[key]['id'],
                        'access_token': encrypt(
                            patched_data[key]['access_token'].encode('utf-8')
                        )
                    }

                    if key in user_data:
                        qry = services.update(matched_record).values(
                            args
                        )

                    else:
                        qry = services.insert().values(
                            sv_name=svc_name,
                            user_id=user_id,
                            **args
                        )

                    await conn.execute(qry)

        except IntegrityError as e:
            if e.pgcode == errorcodes.UNIQUE_VIOLATION:
                raise HandlerError('conflict')
            else:
                raise

        else:
            # Send a notification about the patch
            patched_data['id'] = user_id
            patch = jsonpatch.JsonPatch.from_diff(user_data, patched_data)

            notify = helpers['notify']
            json_data = '{{"user_id": {}, "ops": {} }}'.format(
                user_id, patch
            )
            await notify(json_data.encode('utf-8'))

            return ops


class HandlerError(Exception, Mapping):
    def __init__(self, error, **fields):
        self._data = dict(error=error, **fields)
        super().__init__(error)

    def __iter__(self):
        yield from self._data

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __hash__(self):
        return hash(frozenset(self._data.items()))
