#!/usr/bin/env python2

import sys, os
import json
import argparse
import praw
import sqlite3
from ConfigParser import SafeConfigParser
from flair import get_css_class, get_value_from_flair

containing_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)
username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
app_key = cfg_file.get('reddit', 'app_key')
app_secret = cfg_file.get('reddit', 'app_secret')
subreddit = cfg_file.get('reddit', 'subreddit')
flair_db = cfg_file.get('trade', 'flair_db')

curs = None

def extant_file(x):
    if not os.path.exists(x):
        raise argparse.ArgumentError("{0} does not exist".format(x))
    return x

def get_fixed_css_classes(curs, file):
    flair_json = json.load(open(file))
    flairs = dict()
    for entry in flair_json:
        if 'flair_text' not in entry:
            continue
        elif 'flair_css_class' not in entry:
            continue
        # check if flair_text is the same as the database
        curs.execute('''SELECT flair_text FROM flair WHERE username=?''', (entry['user'],))
        row = curs.fetchone()
        if row['flair_text'] == entry['flair_text']:
            num = get_value_from_flair(entry['flair_text'])
            if num in flairs.keys():
                flairs[num].append(entry['user'])
            else:
                flairs[num] = [entry['user']]
    
    return flairs


def main():
    #parser = argparse.ArgumentParser(description="Import flairs to subreddit")
    #parser.add_argument("-f", "--file", dest="filename", help="input file", metavar="FILE", type=extant_file, required=True)
    #args = parser.parse_args()

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

    flairs = get_fixed_css_classes(curs, 'mangaswapflairs.json')

    for num, names in flairs.items():
        r.subreddit(subreddit).flair.update(names, text=str(num) + ' Confirmed Trades', css_class=get_css_class(num))

if __name__ == "__main__":
    main()
