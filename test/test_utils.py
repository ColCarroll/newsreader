import os
import json
import datetime
import unittest
from nose.tools import assert_in, assert_is_not_none, assert_almost_equal, assert_equal
from utils import DIR, SAMPLE_CREDS, DATE_FMT, get_creds, seconds_from_now, RedditReader,\
    DBWriter, fetch_raw_data


class MockRedditReader(RedditReader):
    def post(self, url, **kwargs):
        if url == "https://www.reddit.com/api/v1/access_token":
            return {"expires_in": 3600, "access_token": "test"}
        raise ValueError("Bad url")

    def get(self, url, **kwargs):
        if url == "https://www.reddit.com/api/v1/access_token":
            return {"expires_in": 3600, "access_token": str(datetime.datetime.today())}
        raise ValueError("Bad url")

    def get_subreddit_data(self, subreddit, after=None):
        return json.load(
            open(os.path.join(DIR, 'test', 'sample_{}.json'.format(subreddit)), 'r')
            )['data']['children']


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


def test_fetch_raw_data():
    db = DBWriter()
    assert_equal(db._count(), len(fetch_raw_data()))


class TestDBWriter(unittest.TestCase):
    def setUp(self):
        self.db = DBWriter()
        self.db.reader = MockRedditReader('news')
        self.db.table = "test_headlines"

    def tearDown(self):
        self.db.drop_table()

    def test_create_table(self):
        self.assertFalse(self.db._exists())
        self.db.create_table()
        self.assertTrue(self.db._exists())

    def test__article_data(self):
        self.db.create_table()
        self.assertIsNone(self.db._article_data({"id": "not_an_id"}))

    def test_update(self):
        data_size = len(list(self.db.reader.gen_articles()))
        self.db.create_table()
        self.assertEqual(self.db._count(), 0, "No rows should have been added yet")
        self.db.update()
        self.assertEqual(self.db._count(), data_size,
                         "The table should have been updated")
        self.db.update()
        self.assertEqual(
            self.db._count(),
            data_size,
            "Second update shouldn't change anything (count is {:,d} instead of {:d})".format(
                self.db._count(), data_size))


class TestRedditReader(unittest.TestCase):
    def setUp(self):
        self.reader = MockRedditReader('news', cred_file=SAMPLE_CREDS)

    def expire_auth(self):
        creds = get_creds(SAMPLE_CREDS)
        creds["expires"] = (
            datetime.datetime.today() - datetime.timedelta(seconds=100)).strftime(DATE_FMT)
        json.dump(creds, open(SAMPLE_CREDS, 'w'))
        self.reader._creds = None

    def remove_auth(self):
        creds = {k: v for k, v in get_creds(SAMPLE_CREDS).iteritems() if k != 'token'}
        json.dump(creds, open(SAMPLE_CREDS, 'w'))

    def test_get_headers(self):
        self.remove_auth()
        self.assertNotIn("token", self.reader.creds)
        self.assertIn("Authorization", self.reader.headers)
        self.assertIsNotNone(self.reader.headers["Authorization"])
        self.assertIn("token", self.reader.creds, "Accessing headers caches token")

    def test__is_expired(self):
        self.reader.headers
        self.assertFalse(self.reader._is_expired(), "Headers should return unexpired token")
        self.expire_auth()
        self.assertTrue(self.reader._is_expired())

    def test_gen_subreddit(self):
        self.assertGreater(len(list(self.reader.gen_subreddit('news'))), 10)
