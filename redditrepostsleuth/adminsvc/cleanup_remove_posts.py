import sys

import pymysql

from redditrepostsleuth.core.celery.maintenance_tasks import cleanup_removed_posts_batch, cleanup_orphan_image_post
from redditrepostsleuth.core.config import Config
from redditrepostsleuth.core.db.db_utils import get_db_engine
from redditrepostsleuth.core.db.uow.sqlalchemyunitofworkmanager import SqlAlchemyUnitOfWorkManager
from redditrepostsleuth.core.logging import log
from redditrepostsleuth.core.util.helpers import chunk_list

def get_db_conn():
    return pymysql.connect(host=config.db_host,
                           user=config.db_user,
                           password=config.db_password,
                           db=config.db_name,
                           cursorclass=pymysql.cursors.DictCursor)

def get_non_reddit_links(uowm):
    with uowm.start() as uow:
        ids = []
        all_posts = []
        posts = uow.posts.find_all_for_delete_check(hours=1440, limit=2500000)
        for post in posts:
            if 'reddit.com' in post.searched_url or 'redd.it' in post.searched_url:
                continue
            all_posts.append({'id': post.post_id, 'url': post.searched_url})
        chunks = chunk_list(all_posts, 400)
        for chunk in chunks:
            cleanup_removed_posts_batch.apply_async((chunk,), queue='delete')

def get_certain_sites(uowm):
    with uowm.start() as uow:
        ids = []
        all_posts = []
        posts = uow.posts.find_all_for_delete_check(hours=1440, limit=2000000)
        for post in posts:
            if 'reddit' in post.searched_url:
                all_posts.append({'id': post.post_id, 'url': post.searched_url})
        chunks = chunk_list(all_posts, 10)
        for chunk in chunks:
            cleanup_removed_posts_batch.apply_async((chunk,), queue='delete')

def get_all_links():
    conn = get_db_conn()
    batch = []
    all_posts = []
    with conn.cursor() as cur:
        query = f"SELECT post_id, url, post_type FROM reddit_post WHERE last_deleted_check <= NOW() - INTERVAL 90 DAY AND post_type='image'"
        cur.execute(query)
        log.info('Adding items to index')
        for row in cur:
            batch.append({'id': row['post_id'], 'url': row['url']})
            if len(batch) >= 25:
                try:
                    cleanup_removed_posts_batch.apply_async((batch,), queue='image_check')
                    batch = []
                except Exception as e:
                    continue

def get_all_links_last_month():
    conn = get_db_conn()
    batch = []
    with conn.cursor() as cur:
        query = f"SELECT post_id, url, post_type FROM reddit_post WHERE post_type='image' AND created_at >= NOW() - INTERVAL 30 DAY"
        cur.execute(query)
        log.info('Adding items to index')
        for row in cur:
            batch.append({'id': row['post_id'], 'url': row['url']})
            if len(batch) >= 18:
                cleanup_removed_posts_batch.apply_async((batch,), queue='image_check')
                batch = []


def get_all_reddit_links():
    conn = get_db_conn()
    with conn.cursor() as cur:
        query = f"SELECT post_id, url FROM reddit_post WHERE last_deleted_check <= NOW() - INTERVAL 60 DAY LIMIT 4000000"
        cur.execute(query)
        log.info('Adding items to index')
        all_posts = []
        for row in cur:
            if 'reddit' in row['url']:
                all_posts.append({'id': row['post_id'], 'url': row['url']})
        chunks = chunk_list(all_posts, 15)
        for chunk in chunks:
            cleanup_removed_posts_batch.apply_async((chunk,), queue='delete_reddit')

def get_all_links_old(uowm):
    with uowm.start() as uow:
        batch = []
        posts = uow.posts.find_all_for_delete_check(hours=1440, limit=2000000)
        for post in posts:
            batch.append({'id': post.post_id, 'url': post.searched_url})
            if len(batch) >= 15:
                cleanup_removed_posts_batch.apply_async((batch,), queue='delete')
                batch = []


if __name__ == '__main__':

    config = Config('/home/barry/PycharmProjects/RedditRepostSleuth/sleuth_config.json')
    uowm = SqlAlchemyUnitOfWorkManager(get_db_engine(config))

    get_all_links()
    sys.exit()


