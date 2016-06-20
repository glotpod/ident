import pytest

from glotpod.ident import notifications



@pytest.fixture
def events(monkeypatch, model):
    items = []

    def notify(_, user_id, type, scope, payload):
        event = {k: v for k, v in locals().items() if k not in ('items', '_')}
        items.append(event)

    monkeypatch.setattr(notifications.Sender, 'notify', notify)

    return items


def test_patch_user_notification(model, client, events):
    id = model.add_user(name="James Slater", email_address="js@p.net")
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
    data['services'] = {}

    assert events == [{
        'user_id': result.json['id'], 'type': 'urn:glotpod:user:new',
        'scope': 'user+n', 'payload': data
    }]
