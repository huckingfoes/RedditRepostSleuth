import re
import time
from typing import List
from time import perf_counter
from praw import Reddit
from praw.models import Comment, Submission
from datetime import datetime

from redditrepostsleuth.common.config.constants import NO_LINK_SUBREDDITS
from redditrepostsleuth.common.config.replytemplates import UNSUPPORTED_POST_TYPE, UNKNOWN_COMMAND, STATS, WATCH_NOT_OC, \
    WATCH_DUPLICATE, WATCH_ENABLED, WATCH_NOT_FOUND, WATCH_DISABLED, LINK_ALL, REPOST_NO_RESULT, IMAGE_REPOST_ALL, \
    IMAGE_REPOST_SHORT, SIGNATURE, IMAGE_REPOST_SHORT_NO_LINK, SIGNATURE_NO_LINK, REPOST_MESSAGE_TEMPLATE, \
    REPOST_MESSAGE_TEMPLATE_NO_LINK, FAILED_TO_LEAVE_RESPONSE
from redditrepostsleuth.common.exception import ImageConversioinException, NoIndexException
from redditrepostsleuth.common.logging import log
from redditrepostsleuth.common.db.uow.unitofworkmanager import UnitOfWorkManager
from redditrepostsleuth.common.model.db.databasemodels import Summons, RepostWatch, Post
from redditrepostsleuth.common.model.imagematch import ImageMatch

from redditrepostsleuth.common.model.repostresponse import RepostResponseBase
from redditrepostsleuth.common.util.objectmapping import submission_to_post
from redditrepostsleuth.core.duplicateimageservice import DuplicateImageService
from redditrepostsleuth.common.util.reposthelpers import set_shortlink, verify_oc, check_link_repost
from redditrepostsleuth.ingestsvc.util import pre_process_post


class SummonsHandler:
    def __init__(self, uowm: UnitOfWorkManager, image_service: DuplicateImageService, reddit: Reddit, summons_disabled=False):
        self.uowm = uowm
        self.image_service = image_service
        self.reddit = reddit
        self.summons_disabled = summons_disabled

    def handle_repost_request(self, summons: Summons):

        parsed_command = re.search('!repost\s(?P<command>[^\s]+)(?P<subcommand>\s[^\s]+)?', summons.comment_body, re.IGNORECASE)

        log.info('Processing request for comment %s. Body: %s', summons.comment_id, summons.comment_body)



        with self.uowm.start() as uow:
            post = uow.posts.get_by_post_id(summons.post_id)

        if not post:
            log.info('Post ID %s does not exist in database.  Attempting to ingest', summons.post_id)
            self.save_unknown_post(summons.post_id)

        response = RepostResponseBase(summons_id=summons.id)

        if self.summons_disabled:
            log.info('Sending summons disabled message')
            response.message = 'Repost checking is disabled right now.  We\'re working on feedback from the launch. I\'ll be back in 48 hours'
            self._send_response(summons.comment_id, response)
            return

        if post.post_type is None or post.post_type not in ['image', 'link']:
            log.error('Submission has no post hint.  Cannot process summons')
            response.status = 'error'
            response.message = UNSUPPORTED_POST_TYPE
            self._send_response(summons.comment_id, response)
            return

        # We just got the summons flag without a command.  Default to repost check
        if not parsed_command:
            self.process_repost_request(summons, post)
            return

        sub_command = parsed_command.group('subcommand')
        if sub_command:
            sub_command = sub_command.strip()

        # TODO handle case when no command is passed
        if parsed_command.group('command').lower() == 'watch':
            self.process_watch_request(summons, sub_command=sub_command)
        elif parsed_command.group('command').lower() == 'unwatch':
            self.process_unwatch_request(summons)
        elif parsed_command.group('command').lower() == 'stats':
            self.process_stat_request(summons)
        elif parsed_command.group('command').lower() == 'check':
            self.process_repost_request(summons, post, sub_command=sub_command)
        else:
            log.error('Unknown command')
            response.message = UNKNOWN_COMMAND
            self._send_response(summons.comment_id, response)


    def process_stat_request(self, summons: Summons):

        response = RepostResponseBase(summons_id=summons.id)
        with self.uowm.start() as uow:
            video_count = uow.posts.count_by_type('video')
            video_count += uow.posts.count_by_type('hosted:video')
            video_count += uow.posts.count_by_type('rich:video')
            image_count = uow.posts.count_by_type('image')
            text_count = uow.posts.count_by_type('text')
            link_count = uow.posts.count_by_type('link')
            summons_count = uow.summons.get_count()
            post_count = uow.posts.get_count()
            oldest_post = uow.posts.get_oldest_post()

        response.message = STATS.format(
            post_count=post_count,
            images=image_count,
            links=link_count,
            video=video_count,
            text=text_count,
            oldest=str(oldest_post.created_at),
            reposts=0,
            summoned=summons_count
        )

        self._send_response(summons.comment_id, response)

    def process_watch_request(self, summons: Summons, sub_command: str = None):
        # TODO - Add check for existing watch
        response = RepostResponseBase(summons_id=summons.id)
        comment = self.reddit.comment(id=summons.comment_id)
        submission = self.reddit.submission(id=summons.post_id)

        if not verify_oc(submission, self.image_service):
            response.message = WATCH_NOT_OC
            self._send_response(comment, response)
            return

        with self.uowm.start() as uow:
            post_count = uow.posts.count_by_type('image')

        with self.uowm.start() as uow:
            watch = uow.repostwatch.find_existing_watch(comment.author.name, summons.post_id)
            if watch:
                log.info('Found duplicate watch')
                response.message = WATCH_DUPLICATE
                self._send_response(comment, response)
                return

            watch = RepostWatch(post_id=summons.post_id, user=comment.author.name)
            watch.response_type = sub_command if sub_command else 'message'
            log.info('Creating watch request on post %s for user %s', summons.post_id, comment.author.name)
            response.message = WATCH_ENABLED.format(check_count=post_count, response=watch.response_type)

            uow.repostwatch.add(watch)
            # TODO - Probably need to catch exception here
            uow.commit()

        self._send_response(comment, response)

    def process_unwatch_request(self, summons: Summons):
        response = RepostResponseBase(summons_id=summons.id)
        comment = self.reddit.comment(id=summons.comment_id)
        with self.uowm.start() as uow:
            log.debug('Looking up existing watch for post %s from user %s', summons.post_id, comment.author.name)
            watch = uow.repostwatch.find_existing_watch(comment.author.name, summons.post_id)
            if not watch:
                log.debug('Unable to locate existing repost watch')
                response.message = WATCH_NOT_FOUND
                self._send_response(comment, response)
                return
            uow.repostwatch.remove(watch)
            uow.commit()
            response.message = WATCH_DISABLED
            self._send_response(comment, response)

    def process_repost_request(self, summons: Summons, post: Post, sub_command: str = None):
        if post.post_type == 'image':
            self.process_image_repost_request(summons, post, sub_command=sub_command)
        elif post.post_type == 'link':
            self.process_link_repost_request(summons, post, sub_command=sub_command)

    def process_link_repost_request(self, summons: Summons, post: Post, sub_command: str = None):

        response = RepostResponseBase(summons_id=summons.id)
        with self.uowm.start() as uow:
            search_count = (uow.posts.get_newest_post()).id
            result = check_link_repost(post, self.uowm)
            if len(result.matches) > 0:
                response.message = LINK_ALL.format(occurrences=len(result.matches),
                                                   searched=search_count,
                                                   original_href='https://reddit.com' + result.matches[0].perma_link,
                                                   link_text=result.matches[0].perma_link)
            else:
                response.message = REPOST_NO_RESULT.format(total=search_count)
            self._send_response(summons.comment_id, response)

    def process_image_repost_request(self, summons: Summons, post: Post, sub_command: str = None):

        response = RepostResponseBase(summons_id=summons.id)

        post_count = self.image_service.index.get_n_items()

        try:
            start = perf_counter()
            results = self.image_service.check_duplicate(post)
            search_time = perf_counter() - start
        except NoIndexException:
            log.error('No available index for image repost check.  Trying again later')
            return

        with self.uowm.start() as uow:
            newest_post = uow.posts.get_newest_post()

        if not results:
            response.message = REPOST_NO_RESULT.format(total=post_count)
        else:
            # TODO: This is temp until database is backfilled with short links
            with self.uowm.start() as uow:
                for match in results:
                    if not match.post.shortlink:
                        set_shortlink(match.post)
                        uow.posts.update(match.post)
                        uow.commit()

            if results[0].post.shortlink:
                original_link = results[0].post.shortlink
            else:
                original_link = 'https://reddit.com' + results[0].post.perma_link

            if sub_command and sub_command.lower() == 'all':
                response.message = REPOST_MESSAGE_TEMPLATE.format(index_size=self.image_service.index.get_n_items(),
                                                     time=search_time,
                                                     total_posts=newest_post.id,
                                                     oldest=results[0].post.created_at,
                                                     count=len(results),
                                                     link_text=results[0].post.post_id,
                                                     original_link=original_link)
                response.message += self._build_markdown_list(results)
            else:
                if post.subreddit in NO_LINK_SUBREDDITS:
                    response.message = REPOST_MESSAGE_TEMPLATE_NO_LINK.format(index_size=self.image_service.index.get_n_items(),
                                                                      time=search_time,
                                                                      total_posts=newest_post.id,
                                                                      oldest=results[0].post.created_at,
                                                                      count=len(results),
                                                                      orig_id=results[0].post.post_id)
                else:
                    response.message = REPOST_MESSAGE_TEMPLATE.format(index_size=self.image_service.index.get_n_items(),
                                                                      time=search_time,
                                                                      total_posts=newest_post.id,
                                                                      oldest=results[0].post.created_at,
                                                                      count=len(results),
                                                                      link_text=results[0].post.post_id,
                                                                      original_link=original_link)

        self._send_response(summons.comment_id, response, no_link=post.subreddit in NO_LINK_SUBREDDITS)

    def _send_response(self, comment_id: str, response: RepostResponseBase, no_link=False):
        comment = self.reddit.comment(comment_id)
        try:
            log.info('Sending response to summons comment %s. MESSAGE: %s', comment.id, response.message)

            if no_link:
                response.message += SIGNATURE_NO_LINK
            else:
                response.message += SIGNATURE.format()
            reply = comment.reply(response.message)
            if reply.id:
                self._save_response(response, reply.id)
                return
            log.error('Did not receive reply ID when replying to comment')
        except Exception as e:
            log.exception('Problem replying to comment', exc_info=True)

            if hasattr(e, 'error_type') and e.error_type in ['DELETED_COMMENT']:
                response.message = 'COMMENT DELETED'
            else:
                self._send_direct_message(comment, response)
            self._save_response(response, None)

    def _send_direct_message(self, comment: Comment, response: RepostResponseBase):
        log.info('Sending direct message to %s', comment.author.name)
        response.message = FAILED_TO_LEAVE_RESPONSE.format(sub=comment.subreddit_name_prefixed) + response.message
        try:
            r = comment.author.message('Repost Check', response.message)
            self._save_response(response, None)
        except Exception as e:
            log.error('Failed to send private message to %s', comment.author.name)


    def _save_response(self, response: RepostResponseBase, response_id: str):
        with self.uowm.start() as uow:
            summons = uow.summons.get_by_id(response.summons_id)
            if summons:
                summons.comment_reply = response.message
                summons.summons_replied_at = datetime.now()
                summons.comment_reply_id = response_id
                uow.commit()
                log.debug('Committed summons response to database')

    def _build_markdown_list(self, matches: List[ImageMatch]) -> str:
        result = ''
        for match in matches:
            result += '* {} - [{}]({})\n'.format(match.post.created_at, match.post.shortlink, match.post.shortlink)
        return result

    def _save_post(self, post: Post):
        with self.uowm.start() as uow:
            uow.posts.update(post)
            uow.commit()

    def handle_summons(self):
        """
        Continually check the summons table for new requests.  Handle them as they are found
        """
        while True:
            try:
                with self.uowm.start() as uow:
                    summons = uow.summons.get_unreplied()
                    for s in summons:
                        self.handle_repost_request(s)
                time.sleep(2)
            except Exception as e:
                log.exception('Exception in handle summons thread')

    def save_unknown_post(self, post_id: str) -> Post:
        """
        If we received a request on a post we haven't ingest save it
        :param submission: Reddit Submission
        :return:
        """
        # TODO - Deal with case of not finding post ID.  Should be rare since this is triggered directly via a comment
        submission = self.reddit.submission(id=post_id)
        post = pre_process_post(submission_to_post(submission), self.uowm)
        with self.uowm.start() as uow:
            try:
                uow.posts.add(post)
                uow.commit()
                log.debug('Commited Post: %s', post)
            except Exception as e:
                log.exception('Problem saving new post', exc_info=True)

        return post

