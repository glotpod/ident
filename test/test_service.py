import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize('op,arg,expected_err', [
    ('test', b'wdhffeiwu', 'decode_error'),
    ('test', {}, 'bad_request'),
    ('dfjhskdfhj', {}, 'operation_not_found'),
    ('errors', {}, 'invocation_failed'),
    ('bad_data', {}, 'invocation_failed'),
    ('value_err', {}, 'bad_request'),
    ('type_err', {}, 'bad_request'),
    ('handler_err', {'err': 'foo'}, 'foo')
])
async def test_error_handling(caller, op, arg, expected_err):
    # Invalid message pack
    resp = await caller.send(op, arg)
    assert resp['error'] == expected_err


@pytest.mark.asyncio
@pytest.mark.parametrize('arg', [
    {},
    {'foo': 'bar'},
    {'eight': 8, 'nine': 9.000001, 'ten': 'ten'}
])
async def test_response_passthrough(caller, arg):
    resp = await caller.send('echo', arg)
    assert resp['result'] == arg
