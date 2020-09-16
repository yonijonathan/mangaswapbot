#!/usr/bin/env python2

import sys, os
import re
import ast
import praw
import sqlite3
import datetime
from ConfigParser import SafeConfigParser
from datetime import datetime, timedelta
from time import sleep, time
from log_conf import LoggerManager
import argparse

# determine curr or prev month
parser = argparse.ArgumentParser(description="Process flairs")
parser.add_argument("-m", action="store", dest="month", default="curr", help="curr or prev month? (default: curr)")
results = parser.parse_args()
conf_link_id = 'link_id'
if results.month == "prev":
    conf_link_id = 'prevlink_id'

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
link_id = cfg_file.get('trade', conf_link_id)
equal_warning = cfg_file.get('trade', 'equal')
age_warning = cfg_file.get('trade', 'age')
karma_warning = cfg_file.get('trade', 'karma')
dev_warning = cfg_file.get('trade', 'dev')
reply = cfg_file.get('trade', 'reply')
age_check = cfg_file.getint('trade', 'age_check')
karma_check = cfg_file.getint('trade', 'karma_check')
flair_txt_suffix = cfg_file.get('trade', 'flair_txt_suffix')
flair_db = cfg_file.get('trade', 'flair_db')
flair_dev = cfg_file.getint('trade', 'flair_dev')
notrade_flairclass = ast.literal_eval(cfg_file.get('trade', 'notrade_flairclass'))

# Configure logging
logger = LoggerManager().getLogger(__name__)

# pulls incremented value from flair_text
def get_value_from_flair(flair_text):
    # flair_text looks like "5 Confirmed Trades"
    try:
        return int(flair_text[:flair_text.find(' ')])
    except Exception as e:
        logger.error('failed to parse number from flair text')
        raise


# +1 to flair_text
def increment_flair_text(flair_text):
    num = get_value_from_flair(flair_text) + 1
    return str(num) + flair_txt_suffix

def get_css_class(flair_text):
    if type(flair_text) != int:
        i = get_value_from_flair()
    
    if 1 <= i < 5:
        return 'bookbrown'
    elif 5 <= i < 10:
        return 'bookred'
    elif 10 <= i < 15:
        return 'bookorange'
    elif 15 <= i < 20:
        return 'bookyellow'
    elif 20 <= i < 25:
        return 'booklightgreen'
    elif 25 <= i < 30:
        return 'bookgreen'
    elif 30 <= i < 35:
        return 'bookcyan'
    elif 35 <= i < 40:
        return 'bookblue'
    elif 40 <= i < 45:
        return 'bookpurple'
    elif 45 <= i < 50:
        return 'bookpink'
    elif 50 <= i < 60:
        return 'bookbronze'
    elif 60 <= i < 70:
        return 'booksilver'
    elif 70 <= i < 80:
        return 'bookgold'
    elif 80 <= i < 90:
        return 'bookplat'
    elif 90 <= i < 100:
        return 'bookblack'
    elif 100 <= i:
        return 'bookgif'
    else:
        logger.error('negative flair value')


def main():

    def conditions():
        if not hasattr(comment.author, 'name'):
            return False
        if 'confirm' not in comment.body.lower():
            return False
        if 'unconfirm' in comment.body.lower():
            return False
        if 'cant confirm' in comment.body.lower():
            return False
        if 'can\'t confirm' in comment.body.lower():
            return False
        if comment.author.name == username:
            return False
        if comment.is_root is True:
            return False
        if comment.banned_by:
            return False
        return True

    def check_self_reply(comment, parent):
        if comment.author.name == parent.author.name:
            if equal_warning:
                comment.reply(equal_warning)
            comment.report('Flair: Self Reply')
            parent.report('Flair: Self Reply')
            save()
            return False
        return True

    def verify(item):
        karma = item.author.link_karma + item.author.comment_karma
        age = (datetime.utcnow() - datetime.utcfromtimestamp(item.author.created_utc)).days

        curs.execute('''SELECT * FROM flair WHERE username=?''', (item.author.name,))

        row = curs.fetchone()

        if row is not None:
            if not item.author_flair_text:
                item.author_flair_text = '0' + flair_txt_suffix
            if not row['flair_text']:
                db_flair_text = '0' + flair_txt_suffix
            if item.author_flair_text in notrade_flairclass:
                return True
            if (get_value_from_flair(item.author_flair_text) > (get_value_from_flair(row['flair_text']) + int(flair_dev))) or (get_value_from_flair(item.author_flair_text) < (get_value_from_flair(row['flair_text']) - int(flair_dev))):
                logger.info('Rechecking deviation: ' + item.author.name)
                second_chance = next(r.subreddit(subreddit).flair(item.author.name))
                if second_chance['flair_text'] == item.author_flair_text:
                    item.report('Flair: Deviation between DB and Reddit')
                    if dev_warning:
                        item.reply(dev_warning)
                    r.subreddit(subreddit).message('Flair Devation Detected', 'User: /u/' + item.author.name + '\n\nDB: ' + str(row['flair_text']) + '\n\nReddit: ' + str(item.author_flair_text))
                    logger.info('Flair Deviation - User: ' + item.author.name + ', DB: ' + str(row['flair_text']) + ', Reddit: ' + str(item.author_flair_text))
                    save()
                    return True

        if get_value_from_flair(item.author_flair_text) < 1:
            if age < age_check:
                item.report('Flair: Account Age')
                if age_warning:
                    item.reply(age_warning)
                save()
                return False
            if karma < karma_check:
                item.report('Flair: Account Karma')
                if karma_warning:
                    item.reply(karma_warning)
                save()
                return False
        return True

    def values(item):
        if not item.author_flair_text:
            logger.info('Rechecking empty flair: ' + item.author.name)
            second_chance = next(r.subreddit(subreddit).flair(item.author.name))
            if second_chance['flair_text'] == item.author_flair_text:
                item.author_flair_text = '1' + flair_txt_suffix
                item.author_flair_css_class = get_css_class(1)
            else:
                item.author_flair_text = increment_flair_text(item.author_flair_text)
                item.author_flair_css_class = get_css_class(item.author_flair_text)
        elif (item.author_flair_text and (item.author_flair_text in notrade_flairclass)):
            pass
        else:
            item.author_flair_text = increment_flair_text(item.author_flair_text)
            item.author_flair_css_class = get_css_class(item.author_flair_text)
        if not item.author_flair_css_class:
            item.author_flair_css_class = ''

    def flair(item):
        if item.author_flair_text not in notrade_flairclass:
            # Set flair in subreddit
            r.subreddit(subreddit).flair.set(item.author, item.author_flair_text, item.author_flair_css_class)
            logger.info('Set ' + item.author.name + '\'s flair to ' + item.author_flair_text)
            # Set flair in database
            curs.execute('''UPDATE OR IGNORE flair SET flair_text=?, flair_css_class=? WHERE username=?''', (item.author_flair_text, item.author_flair_css_class, item.author.name, ))
            curs.execute('''INSERT OR IGNORE INTO flair (username, flair_text, flair_css_class) VALUES (?, ?, ?)''', (item.author.name, item.author_flair_text, item.author_flair_css_class, ))
            con.commit()

        for com in flat_comments:
            if hasattr(com.author, 'name'):
                if com.author.name == item.author.name:
                    com.author_flair_text = item.author_flair_text

    def save():
        with open(link_id + ".log", 'a') as myfile:
                myfile.write('%s\n' % comment.id)

    try:
        # Load old comments
        with open(link_id + ".log", 'a+') as myfile:
            completed = myfile.read()

        try:
            con = sqlite3.connect(flair_db)
            con.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.exception("Error %s:" % e.args[0])

        curs = con.cursor()

        # Log in
        logger.debug('Logging in as /u/' + username)
        r = praw.Reddit(client_id=app_key,
                        client_secret=app_secret,
                        username=username,
                        password=password,
                        user_agent=username)

        mods = r.subreddit(subreddit).moderator()

        # Get the submission and the comments
        logger.info('Starting to grab comments')
        submission = r.submission(id=link_id)
        submission.comments.replace_more(limit=None, threshold=0)
        flat_comments = submission.comments.list()

        logger.info('Finished grabbing comments')

        for comment in flat_comments:
            if not hasattr(comment, 'author'):
                continue
            if comment.id in completed:
                continue
            if not conditions():
                continue
            parent = [com for com in flat_comments if com.fullname == comment.parent_id][0]
            if not hasattr(parent.author, 'link_karma'):
                continue
            if not check_self_reply(comment, parent):
                continue

            if not comment.author.name.lower() in parent.body.lower():
                continue

            # Check Account Age, Karma, and Flair Deviation
            logger.debug('Verifying comment id: ' + comment.id + ' and parent id: ' + parent.id)
            if not verify(comment):
                continue
            if not verify(parent):
                continue

            # Get Future Values to Flair
            values(comment)
            values(parent)

            # Flairs up in here yo
            flair(comment)
            flair(parent)
            if reply:
                comment.reply(reply)
            save()

        """ useless shit
        for msg in r.inbox.unread(limit=None):
            if not msg.was_comment:
                if msg.author in mods:
                    logger.info('Processing PM from mod: ' + msg.author.name)
                    mod_link = re.search('^(https?:\/\/(?:www\.)?reddit\.com\/r\/.*\/comments\/.{6}\/.*\/.{7}\/)$', msg.body)
                    if not mod_link:
                        msg.reply('You have submitted an invalid URL')
                        msg.mark_as_read()
                        continue
                    else:
                        match = re.search(r'[^/]+(?=\/$|$)', msg.body)
                        check_id = match.group(0)
                        tocheck = r.comment(id=check_id).refresh()
                        flat_comments = tocheck.replies.list()
                        for comment in flat_comments:
                            if not hasattr(comment, 'author'):
                                continue
                            if comment.mod_reports:
                                comment.mod.approve()
                            if comment.author.name == username:
                                comment.mod.remove()
                                continue

                            if parent.mod_reports:
                                parent.mod.approve()

                            parent = tocheck

                            logger.info('Mod - Verifying comment id: ' + comment.id + ' and parent id: ' + parent.id)

                            if not conditions():
                                continue
                            if not hasattr(parent.author, 'link_karma'):
                                continue

                            values(comment)
                            values(parent)

                            flair(comment)
                            flair(parent)
                            if reply:
                                comment.reply(reply)
                            msg.reply('Trade flair added for ' + comment.author.name + ' and ' + parent.author.name)
                            msg.mark_read()
                else:
                    logger.info('Processing PM from user: ' + msg.author.name)
                    msg.reply('[BEEP BOOP! I AM A BOT!](http://i.imgur.com/9dJ2quO.gif)')
                    msg.mark_read()
                """

        con.close()

    except Exception as e:
        logger.error(e)

if __name__ == '__main__':
    main()
