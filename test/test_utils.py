from nose.tools import assert_in, assert_is_not_none
from utils import get_creds, get_headers


def test_get_creds():
    creds = get_creds()
    for key in ('client_id', 'client_secret', "username", "password"):
        assert_in(key, creds)
        assert_is_not_none(creds[key])


def test_get_headers():
    headers = get_headers()
    assert_in("Authorization", headers)
    assert_is_not_none(headers["Authorization"])
