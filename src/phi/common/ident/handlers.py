import json

import jsonpatch

from collections import deque
from collections.abc import Mapping
from functools import reduce
from urllib.parse import parse_qsl

from aiohttp import web
from mimetype_match import AcceptHeader
from psycopg2 import DataError, IntegrityError, errorcodes
from sqlalchemy.sql import select, desc, func
from voluptuous import All, Any, Coerce, Schema, Range, Required, Remove, \
    Length, MultipleInvalid

from phi.common.ident import errors
from phi.common.ident.model import users, services


__all__ = ['AllUsers', 'User']

service_name_map = {'fb': 'facebook', 'gh': 'github'}


class AllUsers(web.View):
    params_schema = Schema({
        'name': str,
        'email': str,
        'page_size': All(Coerce(int), Range(min=1)),
        'after_id': All(Coerce(int), Range(min=1)),
        'before_id': All(Coerce(int), Range(min=1)),
        'first': str
    })

    @staticmethod
    def build_query(params, full=False):
        columns = [users.c.id, users.c.name, users.c.email_address] if full \
                  else [users.c.id]

        query = select(columns)

        query = query.order_by(users.c.id)

        if 'email' in params:
            query = query.where(users.c.email_address == params['email'])

        if 'name' in params:
            search_string = " & ".join(
                "{}:*".format(word) for word in params['name'].split(' ')
            )
            name_vector = func.to_tsvector(users.c.name)

            query = query.where(name_vector.match(search_string))
            query = query.order_by(
                desc(func.ts_rank(name_vector, func.to_tsquery(search_string)))
            )

        # if 'page_size' in params:
        #     query = query.limit(params['page_size'])
        return query

    @staticmethod
    def get_best_mimetype(request, mimetypes):
        # Get the best matching mimetype from the given set, or raise an http
        # error if a good match can't be provided
        if 'accept' in request.headers:
            accept = AcceptHeader(request.headers.get('accept', '*/*'))
            match = accept.get_best_match(mimetypes)

            if match is None:
                raise web.HTTPNotAcceptable

            else:
                return match[1]

        else:
            return mimetypes[0]

    async def get(self):
        mimetype = self.get_best_mimetype(self.request, [
            'application/json', 'application/vnd.phi.resource-url+json'
        ])
        query = self.build_query(self.params, mimetype=='application/json')
        results = []

        async with self.request['db_pool'].acquire() as conn:
            async for row in conn.execute(query):
                item = {col:row[col] for col in row
                        if col in ('id', 'name', 'email_address')}

                if mimetype == 'application/json':
                    item['email'] = item.pop('email_address')
                    item['services'] = {}

                    qry = services.select().where(
                        services.c.user_id == row['id'])

                    async for service_row in conn.execute(qry):
                        name = service_name_map[service_row['sv_name']]
                        item['services'][name] = {'id': service_row['sv_id']}

                else:
                    item = "/{}".format(row['id'])

                results.append(item)

            return web.json_response(results, content_type=mimetype)

    async def post(self):
        try:
            # Make sure the incoming data is in a valid format
            # if request.content_type == "application/x-www-form-urlencoded":
            #     data = user_schema(await request.post())

            # else:
            #     data = user_schema(await request.json())

            # fixme: no standard on nested data structures with urlencoded
            data = User.schema(await self.request.json())

            # Get a database connection from the pool
            async with self.request['db_pool'].acquire() as conn:
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
                raise web.HTTPConflict
            else:
                raise

        else:
            # Construct the
            data['id'] = user_id

            # # Send a notification about the creation of this user
            # await helpers['notify'](json.dumps(data).encode('utf-8'))

            # Construct a URL to the resource
            user_url = self.request.app.router.named_resources()['user'].url(
                parts={'id': user_id}
            )

            # ... and headers
            headers = {'Location': user_url}

            return web.json_response({'id': user_id}, status=201,
                                     headers=headers)

    @property
    def params(self):
        try:
            items = dict(parse_qsl(self.request.query_string))
            return self.params_schema(items)
        except MultipleInvalid:
            raise web.HTTPBadRequest


class User(web.View):
    schema = Schema({
        Remove('id'): int,
        Required('name'): All(str, str.strip, Length(min=1)),
        Required('email'): All(str, str.strip, Length(min=1)),
        'services': {
            Any('github', 'facebook'): {
                Required('id'): All(str, str.strip, Length(min=1))
            }
        },
    })

    async def get(self):
        async with self.request['db_pool'].acquire() as conn:
            return web.json_response(await self.get_user_data(conn))

    async def patch(self):
        supported = ("application/json-patch+json", "application/octet-stream")
        if self.request.content_type not in supported:
            headers = {"Accept-Patch": "application/json-patch+json"}
            raise web.HTTPUnsupportedMediaType(headers=headers)

        async with self.request['db_pool'].acquire() as conn:
            async with conn.begin() as transaction:
                data = await self.get_user_data(conn, lock_rows=True)

                try:
                    ops = await self.request.json()
                    patched = self.schema(jsonpatch.apply_patch(data, ops))
                except (TypeError, ValueError, jsonpatch.InvalidJsonPatch,
                        jsonpatch.JsonPointerException):
                    raise web.HTTPBadRequest
                except MultipleInvalid:
                    raise errors.HTTPUnprocessableEntity

                try:
                    query = users.update() \
                        .where(users.c.id == self.id) \
                        .values(name=patched['name'],
                                email_address=patched['email'])

                    await conn.execute(query)

                    for key, svc_name in (('facebook', 'fb'), ('github', 'gh')):
                        matched_record = (
                            (services.c.user_id == self.id) &
                            (services.c.sv_name == svc_name)
                        )

                        if (key not in patched['services']
                                and key in data['services']):
                            # if the service was there before, it has to be
                            # removed
                            qry = services.delete(matched_record)
                            await conn.execute(qry)

                        elif key in patched['services']:
                            args = {'sv_id': patched['services'][key]['id']}

                            if key in data['services']:
                                qry = services.update(matched_record).values(
                                    args
                                )

                            else:
                                qry = services.insert().values(
                                    sv_name=svc_name,
                                    user_id=self.id,
                                    **args
                                )

                            await conn.execute(qry)

                except IntegrityError as e:
                    if e.pgcode == errorcodes.UNIQUE_VIOLATION:
                        raise web.HTTPConflict
                    else:
                        raise

                else:
                    patched['id'] = self.id
                    return web.json_response(patched)

    async def get_user_data(self, conn, *, id=None, lock_rows=False):
        data = {}
        query = select([users, services], for_update=lock_rows)
        query = query.where(users.c.id == self.id)
        query = query.where(users.c.id == services.c.user_id)

        async for row in conn.execute(query):
            data['id'] = row['id']
            data['name'] = row['name']
            data['email'] = row['email_address']
            data.setdefault('services', {})

            if row['sv_id'] is not None:
                service_data = {'id': row['sv_id']}
                key = 'facebook' if row['sv_name'] == 'fb' else 'github'
                data['services'][key] = service_data

        if not data:
            raise web.HTTPNotFound

        return data

    @property
    def id(self):
        try:
            return int(self.request.match_info['id'])
        except TypeError:
            raise web.HTTPNotFound


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
