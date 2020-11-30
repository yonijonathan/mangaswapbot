#!/usr/bin/env python2

import sys, os
import re
from ConfigParser import SafeConfigParser
import praw
import time
from log_conf import LoggerManager

containing_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
cfg_file = SafeConfigParser()
path_to_cfg = os.path.join(containing_dir, 'config.cfg')
cfg_file.read(path_to_cfg)

username = cfg_file.get('reddit', 'username')
password = cfg_file.get('reddit', 'password')
app_key = cfg_file.get('reddit', 'app_key')
app_secret = cfg_file.get('reddit', 'app_secret')
subreddit = cfg_file.get('reddit', 'subreddit')
curr_id = cfg_file.get('trade', 'link_id')

# configure logging
logger = LoggerManager().getLogger(__name__)

def get_month():
    month = time.strftime('%B')
    return(month)

def login():
    r = praw.Reddit(client_id=app_key,
                    client_secret=app_secret,
                    username=username,
                    password=password,
                    user_agent=username)
    return(r)

def post_thread(r,month):
    post = r.subreddit(subreddit).submit('%s Successful Trade Thread' % month, selftext='''#Welcome to the monthly trade thread!

---
To confirm your transaction for the month of {}, post the following information in a comment below.

* What items were exchanged
* Who you bought/sold/traded with
* A link to the thread where the transaction occurred

Once you have posted this information, the person you bought/sold/traded with will need to reply to your comment with "confirmed" for it to be recognized as a valid transaction.

Click [here](https://www.reddit.com/r/mangaswap/comments/{}) for last month's trade thread.

For any inquiries, feel free to send us a message via [**Mod Mail**](https://www.reddit.com/message/compose?to=%2Fr%2Fmangaswap); DMs will be ignored.

Happy swapping!'''.format(month, curr_id), send_replies=False)
    post.mod.distinguish()
    post.mod.sticky(bottom=False)
    return (post.id)


""" updates trade thread link on sidebar
def change_sidebar(r, post_id, month):
    sb = r.subreddit(subreddit).mod.settings()["description"]
    new_flair = r'[Confirm your Trades](/' + post_id + ')'
    new_sb = re.sub(r'\[Confirm your Trades\]\(\/[a-z0-9]+\)', new_flair, sb, 1)
    r.subreddit(subreddit).mod.update(description=new_sb)
"""

def update_config(post_id):
    cfg_file.set('trade', 'prevlink_id', curr_id)
    cfg_file.set('trade', 'link_id', post_id)
    with open(r'config.cfg', 'wb') as configfile:
        cfg_file.write(configfile)

def main():
    month = get_month()
    r = login()
    post_id = post_thread(r, month)
    #change_sidebar(r, post_id, month)
    update_config(post_id)
    logger.info("Posted Trade Confirmation thread")

if __name__ == '__main__':
    main()
