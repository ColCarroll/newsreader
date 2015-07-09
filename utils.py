import os
import json
import datetime
import requests
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor

DIR = os.path.dirname(os.path.abspath(__file__))
CREDS = os.getenv("CREDS", os.path.join(DIR, '.creds'))
SAMPLE_CREDS = os.getenv("CREDS", os.path.join(DIR, '.sample_creds'))
VERSION = 'v0.0.1'
SUBREDDITS = ("news", "worldnews", "politics")
DATE_FMT = "%Y-%m-%d %H:%M:%S"
FEATURE_COLS = ['title', 'subreddit', 'domain']
LABEL_COL = 'score'


def get_creds(path=CREDS):
    if not os.path.exists(path):
        raise ValueError("You must supply credential json at {}".format(path))
    return json.load(open(path, 'r'))


def seconds_from_now(seconds):
    return datetime.datetime.now() + datetime.timedelta(seconds=seconds)


def epoch():
    return int(datetime.datetime.now().strftime("%s"))


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
        ]
    table = "headlines"

    def __init__(self, *subreddits, **kwargs):
        self._creds = None
        self.cred_file = kwargs.get("cred_file", CREDS)
        self.reader = RedditReader(*subreddits)

    def fetch_raw_data(self):
        return list(
            self._fetch_query("SELECT {} FROM {}".format(
                ",".join(FEATURE_COLS + [LABEL_COL]),
                self.table)))

    @property
    def creds(self):
        if self._creds is None:
            self._creds = get_creds(self.cred_file)
        return self._creds

    @contextmanager
    def connector(self):
        try:
            conn = psycopg2.connect(
                user=self.creds.get('db_user'),
                host=self.creds.get('db_host'),
                database=self.creds.get('database'),
                )
            cur = conn.cursor(cursor_factory=RealDictCursor)
            yield cur
        finally:
            conn.commit()
            cur.close()
            conn.close()

    def _execute_query(self, query, *args):
        with self.connector() as cur:
            cur.execute(query, args)

    def _fetch_query(self, query, *args):
        with self.connector() as cur:
            cur.execute(query, args)
            for row in cur:
                yield row

    def _exists(self):
        query = "SELECT * FROM {} LIMIT 1".format(self.table)
        try:
            self._execute_query(query)
        except psycopg2.ProgrammingError:
            return False
        return True

    def drop_table(self):
        if not self._exists():
            return
        self._execute_query("DROP TABLE {}".format(self.table))

    def create_table(self):
        self._execute_query("CREATE TABLE {} (\n\t{}\n)".format(
            self.table,
            ",\n\t".join([" ".join(j) for j in self.schema])))

    def row_gen(self, article):
        values = []
        for key, _ in self.schema:
            if key == "created_utc":
                values.append(int(article[key]))
            else:
                values.append(unicode(article[key]))
        return values

    def _article_data(self, article):
        row_data = None
        for row_data in self._fetch_query(
                "SELECT id, score FROM {} WHERE id = %s".format(self.table),
                article["id"]):
            pass
        return row_data

    def update(self):
        if not self._exists():
            self.create_table()

        columns = ",".join([j[0] for j in self.schema])
        values = ",".join(["%s" for _ in self.schema])
        update_query = u"UPDATE {} SET score = %s WHERE id = %s".format(self.table)
        insert_query = u"INSERT INTO {} ({}) VALUES ({})".format(self.table, columns, values)
        for article in self.reader.gen_articles():
            article_data = self._article_data(article)
            if article_data is not None:
                if article_data['score'] != article['score']:
                    self._execute_query(update_query, article['score'], article['id'])
            else:
                self._execute_query(insert_query, *self.row_gen(article))

    def _count(self):
        for row in self._fetch_query(
                "SELECT COUNT(*) AS count FROM {}".format(self.table)):
            count = row["count"]
        return count


class RedditReader:
    def __init__(self, *subreddits, **kwargs):
        self.subreddits = subreddits
        self.t = 'day'
        self.min_score = 0
        self.sort = "top"
        self.trailing_look = 10
        self._creds = None
        self._headers = None
        self.kwargs = kwargs
        self._cred_file = self.kwargs.get("cred_file", CREDS)

    def post(self, url, **kwargs):
        return requests.post(url, **kwargs).json()

    def get(self, url, **kwargs):
        return requests.get(url, **kwargs).json()

    @property
    def creds(self):
        if self._creds is None:
            self._creds = get_creds(self._cred_file)
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
                data = self.post("https://www.reddit.com/api/v1/access_token",
                                 auth=client_auth, data=post_data, headers=self._headers)
                self._creds["expires"] = seconds_from_now(data.get('expires_in', 0)).strftime(
                    DATE_FMT)
                self._creds["token"] = "bearer " + data.get("access_token", "")
                json.dump(self._creds, open(self._cred_file, 'w'))
            self._headers["Authorization"] = self.creds["token"]
        return self._headers

    def _is_expired(self):
        now = seconds_from_now(0)
        expires = datetime.datetime.strptime(
            self.creds.get('expires', '2000-1-1 0:00:01'),
            DATE_FMT)
        return now > expires

    def get_url(self, url, **kwargs):
        params = dict(self.params.items() + kwargs.items())
        return self.get(url, headers=self.headers, params=params)

    def get_subreddit_data(self, subreddit, after=None):
        return self.get_url("https://oauth.reddit.com/r/{:s}/top".format(subreddit),
                            after=after)['data']['children']

    def gen_subreddit(self, subreddit):
        keep_looking = 1  # counter to see if we've spotted a popular article recently
        after = None
        while keep_looking > 0:
            keep_looking = 0
            for story in self.get_subreddit_data(subreddit, after):
                data = story['data']
                if data['score'] > self.min_score:
                    yield data
                    keep_looking = self.trailing_look
                else:
                    keep_looking -= 1
                after = data['name']

    def gen_articles(self):
        for subreddit in self.subreddits:
            for j in self.gen_subreddit(subreddit):
                yield j


def fetch_raw_data():
    return DBWriter(*SUBREDDITS).fetch_raw_data()


if __name__ == '__main__':
    writer = DBWriter(*SUBREDDITS)
    writer.reader.t = 'day'
    writer.update()
