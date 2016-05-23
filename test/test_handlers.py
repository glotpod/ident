import asyncio
import json
import logging

import pytest

from webtest_aiohttp import TestApp as WebtestApp
from phi.common.ident.handlers import create_user, get_user, patch_user,\
    HandlerError


@pytest.fixture
def client(app):
    return WebtestApp(app)


@pytest.fixture
def model(model):
    id = model.add_user(name="Ned Stark", email_address="hand@headless.north")
    model.add_github_info(sv_id=1000, access_token="", user_id=id)

    id = model.add_user(name="Jon Snow", email_address="clueless@wall.north")
    model.add_facebook_info(sv_id=1000, access_token="", user_id=id)

    id = model.add_user(name="Rob Stark", email_address="king@deceased.north")
    model.add_github_info(sv_id=25, access_token="", user_id=id)
    model.add_facebook_info(sv_id=75, access_token="", user_id=id)

    return model


@pytest.mark.parametrize('id,expected', [
    (
        1,
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'services': {'github': {'id': '1000', 'access_token': ""}}}
    ),
    (
        2,
        {'id': 2, 'name': "Jon Snow", 'email': "clueless@wall.north",
         'services': {'facebook': {'id': '1000', 'access_token': ""}}}
    ),
    (
        3,
        {'id': 3, 'name': "Rob Stark", 'email': "king@deceased.north",
         'services': {'facebook': {'id': '75', 'access_token': ""},
                      'github': {'id': '25', 'access_token': ""}}}
    ),
    (4, None),
    (0, None),
    ("", None),
    (99232832432423423, None),
    (-1, None)
])
def test_get_user(client, model, id, expected):
    res = client.get("/{id}".format(id=id), expect_errors=True)

    if expected is None:
        assert res.status_code == 404

    else:
        assert res.status_code == 200
        assert res.json == expected


@pytest.mark.parametrize('request_func', [
    # WebtestApp.post,
    WebtestApp.post_json
])
@pytest.mark.parametrize('data', [
    {"name": "Doctor", "email": "twelve@tardis.vortex",
     "services": {"github": {"id": '4000',
                             "access_token": "9784rfaweugfdb9ip8aerwrra"}}},

    {"name": "Clara Oswald", "email": "gone@tardis.vortex",
     "services": {"facebook": {'id': '25',
                               "access_token": "awf897ryuofuisvr"},
                  "github": {'id': '75',
                             "access_token": "urfueisdsfhaiweuahwdiaduhc"}}}
])
def test_create_user(model, client, request_func, data):
    result = request_func(client, "/", data)
    assert result.status_code == 201

    assert 'id' in result.json
    assert isinstance(result.json['id'], int)

    id = result.json.pop('id')
    data['id'] = id

    query = client.get('/{id}'.format(id=id))
    assert query.json == data

    assert "Location" in result.headers
    assert result.headers['Location'] == '/{}'.format(id)


@pytest.mark.parametrize('data', [
    {'name': 9, "email": "twelve@tardis.vortex",
     'services': {'github': {'id': '7000', 'access_token': "9784rfaweugfdb9ip8aerwrra"}}},
    {'email': "twelve@tardis.vortex",
     'services': {'github': {'id': '7000', 'access_token': "9784rfaweugfdb9ip8aerwrra"},
                  'facebook': {'id': '7000', 'access_token': "9784rfaweugfdb9ip8aerwrra"}}},

    {'name': "Doctor", 'email': 0,
     'services': {'github': {'id': '7000', 'access_token': "9784rfaweugfdb9ip8aerwrra"}}},
    {'name': "Doctor",
     'services': {'github': {'id': '7000', 'access_token': "9784rfaweugfdb9ip8aerwrra"}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {'id': '', 'access_token': "9784rfaweugfdb9ip8aerwrra"}}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {'access_token': "9784rfaweugfdb9ip8aerwrra"},
                  'facebook': {'id': '3743', 'access_token': ''}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'facebook': {'id': '', 'access_token': "9784rfaweugfdb9ip8aerwrra"},
                  'github': {'id': '3743', 'access_token': ''}}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'facebook': {'access_token': "9784rfaweugfdb9ip8aerwrra"}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {'id': '7000', 'access_token': -46777}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {}}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'facebook': {}}},

])
def test_create_user_validation_errors(model, client, data):
    result = client.post_json('/', data, expect_errors=True)
    assert result.status_code == 400


@pytest.mark.parametrize('data', [
    # Github id
    {'name': 'Jack Harness', 'email': 'cptjk@tw.erth',
     'services': {'github': {'id': '1000', 'access_token': 'fffdjhf'}}},

    # Facebook id
    {'name': 'Jack Harness', 'email': 'cptjk@tw.erth',
     'services': {'facebook': {'id': '75', 'access_token': 'fffdjhf'}}},

    # Email address
    {'name': 'Jack Harness', 'email': 'clueless@wall.north'}
])
def test_create_user_conflict_errors(model, client, data):
    result = client.post_json('/', data, expect_errors=True)
    assert result.status_code == 409


def test_partially_failed_creation_doesnt_leave_behind_data(model, client):
    data = {'name': 'Peter Jonson', 'email': 'hfg@uf.o.fi',
            'services': {'facebook': {'id': '75', 'access_token': ''}}}
    result = client.post_json('/', data, expect_errors=True)
    assert result.status_code == 409

    # Fix and try again
    data['services']['facebook']['id'] = '76'
    result = client.post_json('/', data)
    assert result.status_code == 201

"""
@pytest.mark.asyncio
@pytest.mark.parametrize('query,expected', [
    (
        {'user_id': 1},
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'picture_url': "http://mock.io/gallows.jpg",
         'github': {'id': 1000, 'access_token': ""}}
    ),
    (
        {'email': 'hand@headless.north'},
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'picture_url': "http://mock.io/gallows.jpg",
         'github': {'id': 1000, 'access_token': ""}}
    ),
    (
        {'facebook_id': 1000},
        {'id': 2, 'name': "Jon Snow", 'email': "clueless@wall.north",
         'facebook': {'id': 1000, 'access_token': ""}}
    ),
    (
        {'facebook_id': 1000, 'user_id': 2},
        {'id': 2, 'name': "Jon Snow", 'email': "clueless@wall.north",
         'facebook': {'id': 1000, 'access_token': ""}}
    ),
    (
        {'github_id': 1000},
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'picture_url': "http://mock.io/gallows.jpg",
         'github': {'id': 1000, 'access_token': ""}}
    ),
    (
        {'github_id': 1000, 'user_id': 1},
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'picture_url': "http://mock.io/gallows.jpg",
         'github': {'id': 1000, 'access_token': ""}}
    ),
])
async def test_get_user(model, helpers, query, expected):
    user = await get_user(helpers, **query)
    assert user == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('query', [
    {'facebook_id': ''},
    {'github_id': 'ranger'},
    {'facebook_id': 40000},
    {'github_id': -403242633240},
    {'github_id': 10876.535},
    {'user_id': ''},
    {'user_id': 'ewdjdsfkjd'},
    {'user_id': 10.38630},
    {'user_id': 0},
    {'user_id': 10023483283427},
    {'facebook_id': 'dskfh', 'user_id': 1},
])
async def test_get_user_not_found_errors(model, helpers, query):
    with pytest.raises(HandlerError) as excinfo:
        await get_user(helpers, **query)

    assert excinfo.value['error'] == 'not_found'


@pytest.mark.asyncio
@pytest.mark.parametrize('query', [
    {},
    {'foo': 294239847234832},
    {'github_access_token': "dsfsldjfhsdfkjsdlfjsdlfkjlk"}
])
async def test_get_user_request_errors(model, helpers, query):
    with pytest.raises(TypeError):
        await get_user(helpers, **query)








@pytest.mark.asyncio
@pytest.mark.parametrize('ops, user_id, expected', [
    (
        [{'op': 'replace', 'path': '/picture_url', 'value': 'foo'},
         {'op': 'test', 'path': '/github/id', 'value': 1000}],
        1,
        {'name': "Ned Stark", 'email': "hand@headless.north",
         'picture_url': "foo", 'id': 1,
         'github': {'id': 1000, 'access_token': ""}}
    ),
    (
        [{'op': 'add', 'path': '/github/id', 'value': 56498}],
        1,
        {'name': "Ned Stark", 'email': "hand@headless.north", 'id': 1,
         'picture_url': 'http://mock.io/gallows.jpg',
         'github': {'id': 56498, 'access_token': ""}}
    ),
    (
        [{'op': 'add', 'path': '/github',
          'value': {'id': 56498, 'access_token': ''}}],
        2,
        {'name': "Jon Snow", 'email': "clueless@wall.north", 'id': 2,
         'github': {'id': 56498, 'access_token': ""},
         'facebook': {'id': 1000, 'access_token': ""}}
    ),
    (
        [{'op': 'remove', 'path': '/github'}],
        3,
        {'name': "Rob Stark", 'email': "king@deceased.north", 'id': 3,
         'facebook': {'id': 75, 'access_token': ""}}
    ),

])
async def test_patch_user(model, helpers, ops, user_id, expected):
    await patch_user(helpers, user_id, ops)
    user = await get_user(helpers, user_id=user_id)
    assert user == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('ops, user_id, expected_exc', [
    (
        [{'ofp': 'remove', 'path': '/github'}],
        3,
        ValueError
    ),
    (
        [{'op': 'remove', 'path': 'github'}],
        3,
        ValueError
    ),
    (
        0,
        3,
        ValueError
    ),
    (
        "dsdfdfswdffssdf",
        3,
        ValueError
    ),

    (
        [{'op': 'remove', 'path': '/github'}],
        2,
        'patch_failed'
    ),
    (
        [{'op': 'replace', 'path': '/github', 'value': {}}],
        2,
        'patch_failed'
    ),

    (
        [{'op': 'replace', 'path': '/email', 'value': 'clueless@wall.north'}],
        1,
        'conflict'
    ),
    (
        [{'op': 'replace', 'path': '/github/id', 'value': 25}],
        1,
        'conflict'
    ),
    (
        [{'op': 'replace', 'path': '/facebook/id', 'value': 75}],
        2,
        'conflict'
    ),

    (
        [{'op': 'replace', 'path': '/facebook/id', 'value': 'foo'}],
        2,
        'invalid_patch_result'
    ),
    (
        [{'op': 'move', 'path': '/facebooook', 'from': '/facebook'}],
        2,
        'invalid_patch_result'
    ),
])
async def test_patch_user_errors(model, helpers, ops, user_id, expected_exc):
    handler_error = None

    if isinstance(expected_exc, str):
        handler_error = expected_exc
        expected_exc = HandlerError

    with pytest.raises(expected_exc) as excinfo:
        await patch_user(helpers, user_id, ops)

    if handler_error is not None:
        assert excinfo.value['error'] == handler_error


@pytest.mark.asyncio
@pytest.mark.parametrize('name,func,data,expected', [
    ('patch', patch_user,
     {'user_id': 3, 'ops': [{'op': 'replace', 'path': '/name',
                            'value': 'Tim Brunt'}]},
     {'user_id': 3, 'ops': [{'op': 'replace', 'path': '/name',
                            'value': 'Tim Brunt'}]}),
    ('create', create_user,
     {'name': 'Tim Brunt', 'email': 'tim.brunt@foo.bar',
      'github': {'id': 5555, 'access_token': ''}},
     {'id': 4, 'name': 'Tim Brunt', 'email': 'tim.brunt@foo.bar',
      'github': {'id': 5555, 'access_token': ''}}),
])
async def test_user_notification(
        model, helpers, amqpchannel, name, func, data, expected):
    helpers['notify'] = helpers['notifications-sender'][name]
    recv_queue = asyncio.Queue()

    result = await amqpchannel.queue_declare(exclusive=True, durable=False)
    await amqpchannel.queue_bind(result['queue'], 'amq.topic',
                                 'notifications.user.{}'.format(name))

    async def recv(channel, body, envelope, properties):
        await recv_queue.put(body)

    await amqpchannel.basic_consume(recv, queue_name=result['queue'],
                                    no_ack=True)

    # Call the function
    await func(helpers, **data)

    # Wait for the notification
    item = await asyncio.wait_for(recv_queue.get(), timeout=1)

    # Check that the notification matches what is expected
    assert json.loads(item.decode('utf-8')) == expected
"""
