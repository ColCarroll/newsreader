Newsreader
==========
Uses the reddit api to grab the most popular news headlines (defined more carefully as "any link 
with over 100 votes from /r/news, /r/worldnews, or /r/politics," though this is configurable).
Builds a postgres table with the relevant data in it.  Right now, I am only tracking the highest
score each article gets to -- each run will update an existing score if it is higher (but will not
make two entries for that article).  Future plans are to use the data to predict scores of 
headlines.

Installation
============
Some configuration is required:

1. Create a file .creds in the top directory.  The following fields are required:
    - "username", "password": a valid reddit username and password
    - "client_id", "client_secret": Go to https://github.com/reddit/reddit/wiki/OAuth2#getting-started
    and follow their instructions
    - "db_user", "db_host", "database": Credentials for connecting to a postgresql database.  This 
    assumes you are authenticating using ~/.pgpass.  

2. Have a running postgresql server.  Make sure the database is actually created with, for example, 
    `> CREATE DATABASE reddit_news;`

3. Install python requirements using `virtualenv`.  For example
    ```
        newsreader $ virtualenv venv
        newsreader $ source venv/bin/activate
        (venv) newsreader $ pip install -r requirements.txt
        (venv) newsreader $ python `which nosetests`
    ```
    Note that on OSX, I still need to install the requirements while adding pg_config to my PATH, as 
    in: 

    `PATH=$PATH:/Applications/Postgres.app/Contents/Versions/9.4/bin/; pip install -r requirements.txt`

Running
=======
Running `(venv) newsreader $ python utils.py` will run the code 
`utils.DBWriter('news', 'worldnews', 'politics')`, which will update the table `headlines` in your 
database with any articles on the front page of reddit with >100 points.  It will also update any 
existing articles in your database if the score has changed.
