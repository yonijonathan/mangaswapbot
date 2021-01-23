#!/usr/bin/env python2

import sys, os
from ConfigParser import SafeConfigParser
import praw
import re
import ast
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from time import sleep, time
from log_conf import LoggerManager

# load config file
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
posttitle_regex = cfg_file.get('post_check', 'posttitle_regex')
timestamp_regex = cfg_file.get('post_check', 'timestamp_regex')
rules = cfg_file.get('post_check', 'rules')
upper_hour_buy = cfg_file.getint('post_check', 'upper_hour_buy')
upper_hour_sell = cfg_file.getint('post_check', 'upper_hour_sell')
flairs = ast.literal_eval(cfg_file.get('post_check', 'flairs'))

# configure logging
logger = LoggerManager().getLogger(__name__)

# global vars
lastid = ""

# check to see if last posts conflict with current post (rule 2)
def has_been_posted(id, lastpost, post, row, post_type):
    if row is not None:
        if not row[id]:
            lastid = ""
        else:
            lastid = row[id]
        if row[lastpost]:
            if post_type == 'buy':
                if (((((datetime.utcnow() - row[lastpost]).total_seconds() / 3600) < upper_hour_buy) and (lastid != "") and (post.id != lastid) and not post.approved_by)):
                    return True
            else:
                if (((((datetime.utcnow() - row[lastpost]).total_seconds() / 3600) < upper_hour_sell) and (lastid != "") and (post.id != lastid) and not post.approved_by)):
                    return True
    return False

# message if post is repeated in 7 days
def repeat_post(post):
    post.report('Rule 2 - Posting Frequency')
    post.reply('**Removed:** Post frequecy. Please refer to **rule 2** for posting time limits.\n\nIf you believe this is a mistake, please contact the [moderators](https://www.reddit.com/message/compose?to=%2Fr%2Fmangaswap' + subreddit + ').').mod.distinguish()
    post.mod.remove()

def main():
    while True:
        try:
            try:
                con = sqlite3.connect(flair_db, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
                con.row_factory = sqlite3.Row
            except sqlite3.Error, e:
                logger.error("Error %s:" % e.args[0])

            curs = con.cursor()

            logger.debug('Logging in as /u/' + username)
            r = praw.Reddit(client_id=app_key,
                            client_secret=app_secret,
                            username=username,
                            password=password,
                            user_agent=username)

            already_done = []

            while True:
                data = r.subreddit(subreddit).new(limit=20)
                for post in data:
                    if post.id not in already_done:
                        clean_title = unicodedata.normalize('NFKD', post.title).encode('ascii', 'ignore')
                        removedpost = False
                        checktimestamp = False
                        noreply = False

                        already_done.append(post.id)
                        if (not re.search(posttitle_regex, post.title, re.IGNORECASE)) and not post.distinguished:
                            if post.author.name != username:
                                logger.warn('BAD POST (format) - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name)
                                if not post.approved_by:
                                    post.report('Bad title')
                                    post.reply('**Removed:** Incorrect title. Please refer to the "posting format" section of the sidebar.').mod.distinguish()
                                    post.mod.remove()
                                else:
                                    logger.warn('Bad post approved by: ' + post.approved_by)
                        else:
                            log_msg = ""
                            log_msg_level = ""
                            if not post.distinguished:
                                for f in flairs:
                                    if post.link_flair_text:
                                        if post.link_flair_text == f['name']:
                                            log_msg = 'GOOD POST (*' + f['name'] + ") - " + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                            if f['timestamp_check']:
                                                checktimestamp = True
                                            if f['no_reply']:
                                                noreply = True
                                            break
                                    elif re.search(f['regex'], post.title, re.IGNORECASE):
                                        post.link_flair_text = f['name']
                                        post.mod.flair(text=f['name'], css_class=f['class'])
                                        log_msg = 'GOOD POST (' + f['name'] + ") - " + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                        if f['timestamp_check']:
                                            checktimestamp = True
                                        if f['no_reply']:
                                            noreply = True
                                        break

                            if checktimestamp:
                                if not re.search(timestamp_regex, post.selftext, re.IGNORECASE):
                                    log_msg = 'BAD POST (timestamp) - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    post.report('Missing photos')
                                    post.reply('**Removed:** Missing photos. **Do not delete or repost**, just add your photos to the post and send a modmail indicating they\'ve been added.').mod.distinguish()
                                    post.mod.remove()
                                    removedpost = True

                            curs.execute('''SELECT username, lastbuyid, lastsellid, lasttradeid, lastbuypost as "lastbuypost [timestamp]", lastsellpost as "lastsellpost [timestamp]", lasttradepost as "lasttradepost [timestamp]" FROM flair WHERE username=?''', (post.author.name,))

                            row = curs.fetchone()
                            # ensure that time of last post is > 7 days
                            if 'buy' in post.title.lower():
                                if has_been_posted('lastbuyid', 'lastbuypost', post, row, 'buy'):
                                    log_msg = 'BAD POST (7 day) BUYING - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True
                                elif has_been_posted('lastsellid', 'lastsellpost', post, row, 'sell') and has_been_posted('lasttradeid', 'lasttradepost', post, row, 'trade'):
                                    log_msg = 'BAD POST (7 day) BUYING - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True

                            elif 'sell' in post.title.lower():
                                if has_been_posted('lastsellid', 'lastsellpost', post, row, 'sell'):
                                    log_msg = 'BAD POST (7 day) SELLING - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True
                                elif has_been_posted('lastbuyid', 'lastbuypost', post, row, 'buy') and has_been_posted('lasttradeid', 'lasttradepost', post, row, 'trade'):
                                    log_msg = 'BAD POST (7 day) SELLING - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True

                            elif 'trading' in post.title.lower() or 'trade' in post.title.lower():
                                if has_been_posted('lasttradeid', 'lasttradepost', post, row, 'trading'):
                                    log_msg = 'BAD POST (7 day) TRADE - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True
                                elif has_been_posted('lastbuyid', 'lastbuypost', post, row, 'buy') and has_been_posted('lastsellid', 'lastsellpost', post, row, 'sell'):
                                    log_msg = 'BAD POST (7 day) TRADE - ' + post.id + ' - ' + clean_title + ' - by: ' + post.author.name
                                    log_msg_level = 'warn'
                                    repeat_post(post)
                                    removedpost = True

                            # check comments for info from bot
                            if not post.distinguished:
                                post.comments.replace_more(limit=0)
                                flat_comments = post.comments.list()
                                botcomment = 0
                                for comment in flat_comments:
                                    if hasattr(comment.author, 'name'):
                                        if comment.author.name == username:
                                            if not removedpost:
                                                botcomment = 1
                                # otherwise spit out user information
                                # have to check both flair class and regex match.  (flair class is none if just set)
                                if botcomment == 0 and (not noreply):
                                    age = str(datetime.utcfromtimestamp(post.author.created_utc))
                                    if str(post.author_flair_text) == "None":
                                        heatware = "None"
                                    else:
                                        heatware = "[" + str(post.author_flair_text) + "](" + str(post.author_flair_text) + ")"
                                    tradecount = post.author_flair_text.split()[0] if post.author_flair_text else 'None'
                                    post.reply('* Username: /u/' + str(post.author.name) + '\n* Join date: ' + age + '\n* Link karma: ' + str(post.author.link_karma) + '\n* Comment karma: ' + str(post.author.comment_karma) + '\n* Confirmed trades: ' + str(tradecount) + '\n\n Make sure to read ***all*** of the rules prior to buying or selling! PayPal G&S is the ***only*** acceptable form of payment.').mod.distinguish()
                            if (log_msg_level == 'warn'):
                                logger.warning(log_msg)
                            else:
                                logger.info(log_msg)

                            # add time to sql
                            if row is not None:
                                if (post.id == lastid):
                                    continue
                            if (removedpost):
                                continue
                            # updates last post in database
                            if 'buy' in post.title.lower():
                                curs.execute('''UPDATE OR IGNORE flair SET lastbuypost=?, lastbuyid=? WHERE username=?''', (datetime.utcnow(), post.id, post.author.name, ))
                                curs.execute('''INSERT OR IGNORE INTO flair (username, lastbuypost, lastbuyid) VALUES (?, ?, ?)''', (post.author.name, datetime.utcnow(), post.id, ))
                            elif 'sell' in post.title.lower():
                                curs.execute('''UPDATE OR IGNORE flair SET lastsellpost=?, lastsellid=? WHERE username=?''', (datetime.utcnow(), post.id, post.author.name, ))
                                curs.execute('''INSERT OR IGNORE INTO flair (username, lastsellpost, lastsellid) VALUES (?, ?, ?)''', (post.author.name, datetime.utcnow(), post.id, ))
                            elif 'trading' in post.title.lower() or 'trade' in post.title.lower():
                                curs.execute('''UPDATE OR IGNORE flair SET lasttradepost=?, lasttradeid=? WHERE username=?''', (datetime.utcnow(), post.id, post.author.name, ))
                                curs.execute('''INSERT OR IGNORE INTO flair (username, lasttradepost, lasttradeid) VALUES (?, ?, ?)''', (post.author.name, datetime.utcnow(), post.id, ))
                            con.commit()

                logger.debug('Sleeping for 2 minutes')
                sleep(120)
        except Exception as e:
            logger.error(e)
            sleep(120)

if __name__ == '__main__':
    main()
