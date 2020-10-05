#!/usr/bin/env python2

import sys, os
import json
import argparse
import praw
from ConfigParser import SafeConfigParser
from flair import get_css_class

containing_dir = os.path.dirname(os.path.abspath(os.path.dirname(sys.argv[0])))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)
username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
app_key = cfg_file.get('reddit', 'app_key')
app_secret = cfg_file.get('reddit', 'app_secret')
subreddit = cfg_file.get('reddit', 'subreddit')

curs = None

def extant_file(x):
    if not os.path.exists(x):
        raise argparse.ArgumentError("{0} does not exist".format(x))
    return x

def get_fixed_css_classes(file):
    flair_json = json.load(open(file))
    out = list()
    for entry in flair_json:
        if entry['flair_text'] is None:
            continue
        elif entry['flair_css_class'] is None:
            continue
        # check if flair_text is the same as the database
        curs.execute('''SELECT flair_text FROM flair WHERE username=?''', (entry['user']))
        row = curs.fetchone()
        if row['flair_text'] == entry['flair_text']:
            entry['flair_css_class'] = get_css_class(entry['flair_text'])
            out.append(entry)

    return out

def main():
    parser = argparse.ArgumentParser(description="Import flairs to subreddit")
    parser.add_argument("-f", "--file", dest="filename", help="input file", metavar="FILE", type=extant_file, required=True)
    args = parser.parse_args()

    r = praw.Reddit(client_id=app_key,
                    client_secret=app_secret,
                    username=username,
                    password=password,
                    user_agent=username)

    try:
        con = sqlite3.connect(flair_db)
        con.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        logger.exception("Error %s:" % e.args[0])
    
    curs = con.cursor()

    r.subreddit(subreddit).flair.update(get_fixed_css_classes(args.filename))

if __name__ == "__main__":
    main()