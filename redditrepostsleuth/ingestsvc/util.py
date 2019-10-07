from redditrepostsleuth.common.db.uow.unitofworkmanager import UnitOfWorkManager
from redditrepostsleuth.common.exception import ImageConversioinException
from redditrepostsleuth.common.logging import log
from redditrepostsleuth.common.model.db.databasemodels import RedditImagePost, Post
from redditrepostsleuth.common.util.imagehashing import set_image_hashes

from hashlib import md5

def pre_process_post(post: Post, uowm: UnitOfWorkManager) -> Post:

    with uowm.start() as uow:
        if post.post_type == 'image':
            try:
                image_post = process_image_post(post)
                uow.image_post.add(image_post)
            except ImageConversioinException as e:
                log.error('Failed to get image hashes on new post')
                pass
        elif post.post_type == 'link':
            url_hash = md5(post.url.encode('utf-8'))
            post.url_hash = url_hash.hexdigest()
            log.debug('Set URL hash for post %s', post.post_id)
        elif post.post_type == 'hosted:video':
            # process_video.apply_async((post.url, post.post_id), queue='video_hash')
            pass

        try:
            uow.commit()
            log.debug('Commited Post: %s', post)
        except Exception as e:
            log.exception('Error saving new post', exc_info=True)

    return post

def process_image_post(post: Post) -> RedditImagePost:
    set_image_hashes(post)
    image_post = RedditImagePost()
    image_post.post_id = post.post_id
    image_post.dhash_h = post.dhash_h
    image_post.dhash_v = post.dhash_v
    return image_post
