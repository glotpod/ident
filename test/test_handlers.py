import re

import pytest

from urllib.parse import urlencode

from hypothesis import given
from hypothesis.strategies import integers
from webtest_aiohttp import TestApp as WebtestApp


@pytest.fixture
def client(app):
    return WebtestApp(app)


@pytest.fixture
def model(model):
    id = model.add_user(name="Ned Stark", email_address="hand@headless.north")
    model.add_github_info(sv_id=1000, user_id=id)

    id = model.add_user(name="Jon Snow", email_address="clueless@wall.north")
    model.add_facebook_info(sv_id=1000, user_id=id)

    id = model.add_user(name="Robb Stark", email_address="king@deceased.north")
    model.add_github_info(sv_id=25, user_id=id)
    model.add_facebook_info(sv_id=75, user_id=id)

    return model


@pytest.mark.parametrize('id,expected', [
    (
        1,
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'services': {'github': {'id': '1000'}}}
    ),
    (
        2,
        {'id': 2, 'name': "Jon Snow", 'email': "clueless@wall.north",
         'services': {'facebook': {'id': '1000'}}}
    ),
    (
        3,
        {'id': 3, 'name': "Robb Stark", 'email': "king@deceased.north",
         'services': {'facebook': {'id': '75'},
                      'github': {'id': '25'}}}
    ),
    (4, None),
    (0, None),
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
     "services": {"github": {"id": '4000'}}},

    {"name": "Clara Oswald", "email": "gone@tardis.vortex",
     "services": {"facebook": {'id': '25'},
                  "github": {'id': '75'}}}
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
     'services': {'github': {'id': '7000'}}},
    {'email': "twelve@tardis.vortex",
     'services': {'github': {'id': '7000'},
                  'facebook': {'id': '7000'}}},

    {'name': "Doctor", 'email': 0,
     'services': {'github': {'id': '7000'}}},
    {'name': "Doctor",
     'services': {'github': {'id': '7000'}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {'id': ''}}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'github': {},
                  'facebook': {'id': '3743'}}},

    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'facebook': {'id': ''},
                  'github': {'id': '3743'}}},
    {'name': "Doctor", 'email': "twelve@tardis.vortex",
     'services': {'facebook': {}}},

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
     'services': {'github': {'id': '1000'}}},

    # Facebook id
    {'name': 'Jack Harness', 'email': 'cptjk@tw.erth',
     'services': {'facebook': {'id': '75'}}},

    # Email address
    {'name': 'Jack Harness', 'email': 'clueless@wall.north'}
])
def test_create_user_conflict_errors(model, client, data):
    result = client.post_json('/', data, expect_errors=True)
    assert result.status_code == 409


def test_partially_failed_creation_doesnt_leave_behind_data(model, client):
    data = {'name': 'Peter Jonson', 'email': 'hfg@uf.o.fi',
            'services': {'facebook': {'id': '75'}}}
    result = client.post_json('/', data, expect_errors=True)
    assert result.status_code == 409

    # Fix and try again
    data['services']['facebook']['id'] = '76'
    result = client.post_json('/', data)
    assert result.status_code == 201


@pytest.mark.parametrize('params, matched_ids', [
    ({}, [1, 2, 3]),
    (dict(email="clueless@wall.north"), [2]),
    (dict(name="Robb Stark"), [3]),

    (dict(name="Stark"), [1, 3]),
    (dict(name="Snow", email="clueless@wall.north"), [2]),
    (dict(name="Stark", email="clueless@wall.north"), []),
    (dict(name="Rickon Stark"), []),
])
def test_search_users(model, client, params, matched_ids):
    result = client.get('/?{}'.format(urlencode(params)))
    assert result.status_code == 200
    assert [item['id'] for item in result.json] == matched_ids


@given(integers(min_value=1))
def test_search_item_limit(model, client, page_size):
    result = client.get('/?page_size={}'.format(page_size))
    assert result.status_code == 200
    assert len(result.json) <= page_size


def test_search_page_links(model, client):
    def get_links(links_header):
        return {
            match[0]: match[1]
            for match in
            re.findall(r"<(.*?)>;\srel=([a-z]+)", links_header, re.I)
        }

    result = client.get('/?page_size=1')
    first_set = result.json

    # Check for a link header
    assert "link" in result.headers

    # Destructure the link header
    links = get_links(result.headers['link'])

    # There should be at least three pages
    assert 'next' in links
    assert 'previous' not in links

    # Get the second page, and check its links
    result = client.get(links['next'])
    second_set = result.json
    links = get_links(result.headers['link'])
    assert 'next' in links
    assert 'previous' in links

    # Check that getting the previous link from the second is the same as
    # getting the first page
    result = client.get(links['previous'])
    assert result.json == first_set

    # Go to the last page and check its links
    result = client.get(links['next'])
    links = get_links(result.headers['link'])
    assert 'next' not in links
    assert 'previous' not in links

    # Check that getting the previous link from the third page is the same
    # as getting the second page
    result = client.get(links['previous'])
    assert result.json == second_set


@pytest.mark.parametrize('mediatype, expected', [
    (
        'application/json',
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'services': {'github': {'id': '1000'}}}
    ),
    (
        None,
        {'id': 1, 'name': "Ned Stark", 'email': "hand@headless.north",
         'services': {'github': {'id': '1000'}}}
    ),
    ('application/vnd.glotpod.resource-url+json', '/1'),

    ('text/plain', None),
    ('text/json', None),
    ('text/html', None),
    ('application/vnd.glotpod.links+json', None)
])
def test_search_page_media_types(model, client, mediatype, expected):
    headers = {"Accept": mediatype} if mediatype else {}
    result = client.get("/", headers=headers, expect_errors=expected is None)

    if expected is None:
        assert result.status_code == 406

    else:
        assert result.status_code == 200
        assert result.json[0] == expected


@pytest.mark.parametrize('ops, id, expected', [
    (
        [{'op': 'test', 'path': '/services/github/id', 'value': '1000'}],
        1,
        {'name': "Ned Stark", 'email': "hand@headless.north",
         'id': 1, 'services': {'github': {'id': '1000'}}}
    ),
    (
        [{'op': 'add', 'path': '/services/github/id', 'value': '56498'}],
        1,
        {'name': "Ned Stark", 'email': "hand@headless.north", 'id': 1,
         'services': {'github': {'id': '56498'}}}
    ),
    (
        [{'op': 'add', 'path': '/services/github', 'value': {'id': '56498'}}],
        2,
        {'name': "Jon Snow", 'email': "clueless@wall.north", 'id': 2,
         'services': {'github': {'id': '56498'}, 'facebook': {'id': '1000'}}}
    ),
    (
        [{'op': 'remove', 'path': '/services/github'}],
        3,
        {'name': "Robb Stark", 'email': "king@deceased.north", 'id': 3,
         'services': {'facebook': {'id': '75'}}}
    ),

])
def test_patch_user(model, client, ops, id, expected):
    headers = {'Content-Type': 'application/json-patch+json'}
    result = client.patch_json("/{}".format(id), ops, headers=headers)
    assert result.status_code == 200

    assert client.get("/{}".format(id)).json == expected


@pytest.mark.parametrize('ops,id,code', [
    (
        [{'ofp': 'remove', 'path': '/services/github'}],
        3,
        400
    ),
    (
        [{'op': 'remove', 'path': 'services/github'}],
        3,
        400
    ),
    (0, 3, 400),
    ("dfdfsdfsdsgetefddfsdfsdfdf", 3, 400),
    (
        [{'op': 'remove', 'path': '/path/doesnt/exist'}],
        1,
        400
    ),
    (
        [{'op': 'replace', 'path': '/path/doesnt/exist', 'value': {}}],
        1,
        400
    ),

    (
        [{'op': 'replace', 'path': '/email', 'value': 'clueless@wall.north'}],
        1,
        409
    ),
    (
        [{'op': 'replace', 'path': '/services/github/id', 'value': '25'}],
        1,
        409
    ),

    (
        [{'op': 'replace', 'path': '/email', 'value': 34}],
        2,
        422
    ),
    (
        [{'op': 'move', 'path': '/facebooook', 'from': '/services/facebook'}],
        2,
        422
    ),
])
def test_patch_user_errors(model, client, ops, id, code):
    headers = {'Content-Type': 'application/json-patch+json'}
    result = client.patch_json("/{}".format(id), ops, expect_errors=True,
                               headers=headers)
    assert result.status_code == code


def test_patch_user_invalid_media_type(model, client):
    result = client.patch_json("/1", [], expect_errors=True)
    assert result.status_code == 415
