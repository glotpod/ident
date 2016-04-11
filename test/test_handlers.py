import asyncio
import json
import logging

import pytest
from glotpod.ident.handlers import create_user, get_user, patch_user,\
    HandlerError


@pytest.yield_fixture
def helpers(ident, event_loop):
    event_loop.run_until_complete(ident.setup())

    h = dict(ident)
    h['log'] = logging.getLogger('glotpod.ident.test.user')
    h['notify'] = h['notifications-sender']['test']
    yield h

    event_loop.run_until_complete(ident.cleanup())


@pytest.fixture
def model(model):
    id = model.add_user(name="Ned Stark", email_address="hand@headless.north",
                        picture_url="http://mock.io/gallows.jpg")
    model.add_github_info(sv_id=1000, access_token="", user_id=id)

    id = model.add_user(name="Jon Snow", email_address="clueless@wall.north")
    model.add_facebook_info(sv_id=1000, access_token="", user_id=id)

    id = model.add_user(name="Rob Stark", email_address="king@deceased.north")
    model.add_github_info(sv_id=25, access_token="", user_id=id)
    model.add_facebook_info(sv_id=75, access_token="", user_id=id)

    return model


@pytest.mark.asyncio
@pytest.mark.parametrize('query,expected', [
    (
        {'user_id': 1},
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
@pytest.mark.parametrize('data', [
    {"name": "Doctor", "email": "twelve@tardis.vortex",
     "github": {"id": 4000,
                "access_token": "9784rfaweugfdb9ip8aerwrra"}},
    {"name": "Clara Oswald", "email": "gone@tardis.vortex",
     "picture_url": "https://www.google.com/url?sa=i&rct=j&q=&esrc=s&"
                    "source=images&cd=&cad=rja&uact=8&ved=0ahUKEwjx3c"
                    "LB3_rLAhXMWx4KHYdKAiUQjRwIBw&url=http%3A%2F%2Fww"
                    "w.dailymail.co.uk%2Ftvshowbiz%2Farticle-2121133%"
                    "2FDoctor-Whos-new-companion-Jenna-Louise-Coleman"
                    "-talks-landing-coveted-role.html&bvm=bv.11844345"
                    "1,d.dmo&psig=AFQjCNF4brmEq_z7Fa8gEFG0GGX046yB2w&"
                    "ust=1460057318530047",
     "facebook": {'id': 25, "access_token": "awf897ryuofuisvr"},
     "github": {'id': 75, "access_token": "urfueisdsfhaiweuahwdiaduhc"}}
])
async def test_create_user(model, helpers, data):
    result = await create_user(helpers, **data)
    data['id'] = result['user_id']
    assert (await get_user(helpers, user_id=result['user_id'])) == data


@pytest.mark.asyncio
@pytest.mark.parametrize('data', [
    # Github id
    {'name': 'Jack Harness', 'email': 'cptjk@tw.erth',
     'github': {'id': 1000, 'access_token': 'fffdjhf'}},

    # Facebook id
    {'name': 'Jack Harness', 'email': 'cptjk@tw.erth',
     'facebook': {'id': 75, 'access_token': 'fffdjhf'}},

    # Email address
    {'name': 'Jack Harness', 'email': 'clueless@wall.north',
     'facebook': {'id': 2332923, 'access_token': ''}}
])
async def test_create_user_conflict_errors(model, helpers, data):

    with pytest.raises(HandlerError) as excinfo:
        await create_user(helpers, **data)

    assert excinfo.value['error'] == 'conflict'


@pytest.mark.asyncio
@pytest.mark.parametrize('data', [
    {'name': 9, "email": "twelve@tardis.vortex",
     'github': {'id': 7000, 'access_token': "9784rfaweugfdb9ip8aerwrra"}},
    {'email': "twelve@tardis.vortex",
     'github': {'id': 7000, 'access_token': "9784rfaweugfdb9ip8aerwrra"},
     'facebook': {'id': 7000, 'access_token': "9784rfaweugfdb9ip8aerwrra"}},

    {'name': "Doctor", 'email': 0,
     'github': {'id': 7000, 'access_token': "9784rfaweugfdb9ip8aerwrra"}},
    {'name': "Doctor",
     'github': {'id': 7000, 'access_token': "9784rfaweugfdb9ip8aerwrra"}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': {'id': '', 'access_token': "9784rfaweugfdb9ip8aerwrra"}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': {'access_token': "9784rfaweugfdb9ip8aerwrra"},
     'facebook': {'id': 3743, 'access_token': ''}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'facebook': {'id': '', 'access_token': "9784rfaweugfdb9ip8aerwrra"},
     'github': {'id': 3743, 'access_token': ''}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'facebook': {'access_token': "9784rfaweugfdb9ip8aerwrra"}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': {'id': 7000, 'access_token': -46777}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': {'id': 7000}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': {}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'github': 36556},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'facebook': {}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'facebook': 32872836},

])
async def test_create_user_validation_errors(model, helpers, data):
    with pytest.raises(ValueError):
        await create_user(helpers, **data)


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
