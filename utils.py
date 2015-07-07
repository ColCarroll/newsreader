import os
import json
import datetime
import requests
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
import dateutil.parser

DIR = os.path.dirname(os.path.abspath(__file__))
CREDS = os.getenv("CREDS", os.path.join(DIR, '.creds'))
VERSION = 'v0.0.1'
SUBREDDITS = ("news", "worldnews", "politics")


def get_creds():
    if not os.path.exists(CREDS):
        raise ValueError("You must supply credential json at {}".format(CREDS))
    return json.load(open(CREDS, 'r'))


def seconds_from_now(seconds):
    return datetime.datetime.now() + datetime.timedelta(seconds=seconds)


class DBWriter:
    schema = [
        ("created_utc", "BIGINT"),
        ("domain", "TEXT"),
        ("id", "TEXT"),
        ("permalink", "TEXT"),
        ("score", "INTEGER"),
        ("subreddit", "TEXT"),
        ("title", "TEXT"),
        ("url", "TEXT"),
        ("modified_utc", "BIGINT")
        ]

    def __init__(self):
        self._creds = None

    @property
    def creds(self):
        if self._creds is None:
            self._creds = get_creds()
        return self._creds

    @contextmanager
    def connector():
        creds = get_creds()
        try:
            conn = psycopg2.connect(
                user=creds.get('db_user'),
                host=creds.get('db_host'),
                database=creds.get('database'),
                )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            yield cur
        finally:
            conn.commit()
            cur.close()
            conn.close()

class Reader:
    def __init__(self, *subreddits):
        self.subreddits = subreddits
        self.t = 'day'
        self.min_score = 100
        self.sort = "top"
        self.trailing_look = 10
        self._creds = None
        self._headers = None

    @property
    def creds(self):
        if self._creds is None:
            self._creds = get_creds()
        return self._creds

    @property
    def params(self):
        return {"t": self.t, "sort": self.sort, "limit": 100}

    @property
    def headers(self):
        if self._headers is None:
            self._headers = {"User-Agent": "osx:newsreader:{} (by /u/{})".format(
                VERSION, self.creds["username"])}
            if "token" not in self.creds or self._is_expired():
                client_auth = requests.auth.HTTPBasicAuth(
                    self.creds['client_id'], self.creds['client_secret'])
                post_data = {"grant_type": "password",
                             "username": self.creds['username'],
                             "password": self.creds["password"]}
                response = requests.post("https://www.reddit.com/api/v1/access_token",
                                         auth=client_auth, data=post_data, headers=self._headers)
                data = response.json()
                self._creds["expires"] = seconds_from_now(data.get('expires_in', 0)).strftime(
                    "%Y-%m-%d %H:%M:%S")
                self._creds["token"] = "bearer " + data.get("access_token", "")
                json.dump(self._creds, open(CREDS, 'w'))
            self._headers["Authorization"] = self.creds["token"]
        return self._headers

    def _is_expired(self):
        now = seconds_from_now(0)
        expires = dateutil.parser.parse(self.creds.get('expires', '2000-1-1 0:00:01'))
        return now > expires

    def get_url(self, url, **kwargs):
        params = dict(self.params.items() + kwargs.items())
        return requests.get(url, headers=self.headers, params=params).json()

    def gen_articles(self):
        for subreddit in self.subreddits:
            for j in self.gen_subreddit(subreddit):
                yield j

    def gen_subreddit(self, subreddit):
        keep_looking = 1  # counter to see if we've spotted a popular article recently
        after = None
        while keep_looking > 0:
            keep_looking = 0
            data = self.get_url("https://oauth.reddit.com/r/{:s}/top".format(subreddit),
                                after=after)
            for story in data['data']['children']:
                data = story['data']
                if data['score'] > self.min_score:
                    yield data
                    keep_looking = self.trailing_look
                else:
                    keep_looking -= 1
                after = data['name']


if __name__ == '__main__':
    Reader(*SUBREDDITS).print_articles()
