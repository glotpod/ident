import pytest

from glotpod.ident import notifications


@pytest.fixture
def events(monkeypatch):
    items = []

    def notify(_, user_id, type, scope, payload):
        items.append(locals().copy())

    monkeypatch.setattr(notifications.Sender.notify, notify)

    return items


def test_patch_user_notification(model, client, events):
    ops = [{'op': 'replace', 'path': '/name', 'value': 'Tim'}]
    headers = {'Content-Type': 'application/json-patch+json'}

    client.patch_json("/1", ops, headers=headers)

    assert events == [{
        'user_id': 1, 'type': 'urn:glotpod:user:patch',
        'scope': 'user+n', 'payload': ops
    }]


def test_create_user_notification(client, events):
    data = {'name': "James Spark", 'email': 'foo@example.com'}
    result = client.post_json('/', data)

    data['id'] = result.json['id']

    assert events == [{
        'user_id': result.json['id'], 'type': 'urn:glotpod:user:new',
        'scope': 'user+n', 'payload': data
    }]
