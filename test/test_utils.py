import unittest
from nose.tools import assert_in, assert_is_not_none, assert_almost_equal
from utils import get_creds, seconds_from_now, Reader


def test_seconds_from_now():
    tests = [(10, 0), (0, 10), (20, 10), (10, 10)]
    for start, stop in tests:
        assert_almost_equal(
            (seconds_from_now(start) - seconds_from_now(stop)).total_seconds(),
            float(start - stop),
            2,
            "Difference between returned times should be {:d}".format(start - stop))


def test_get_creds():
    creds = get_creds()
    for key in ('client_id', 'client_secret', "username", "password"):
        assert_in(key, creds)
        assert_is_not_none(creds[key])


class TestReader(unittest.TestCase):
    def setUp(self):
        self.reader = Reader('news')

    def test_get_headers(self):
        self.assertIn("Authorization", self.reader.headers)
        self.assertIsNotNone(self.reader.headers["Authorization"])
