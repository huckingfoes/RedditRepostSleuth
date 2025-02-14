import os

from redditrepostsleuth.core.config import Config

config = Config()

broker_url = f'redis://user:{config.redis_password}@{config.redis_host}:{config.redis_port}/0'
result_backend = broker_url
task_serializer = 'pickle'
result_serializer='pickle'
accept_content = ['pickle', 'json']
result_expires = 60
task_routes = {
    'redditrepostsleuth.core.celery.ingesttasks.save_new_post': {'queue': 'postingest'},
    'redditrepostsleuth.core.celery.ingesttasks.ingest_repost_check': {'queue': 'repost2'},
    'redditrepostsleuth.core.celery.reposttasks.check_image_repost_save': {'queue': 'repost_image'},
    'redditrepostsleuth.core.celery.reposttasks.process_repost_annoy': {'queue': 'process_repost'},
    'redditrepostsleuth.core.celery.tasks.link_repost_check': {'queue': 'repost_link'},
    'redditrepostsleuth.core.celery.tasks.log_repost': {'queue': 'logrepost'},
    'redditrepostsleuth.core.celery.maintenance_tasks.update_monitored_sub_stats': {'queue': 'monitored_sub_update'},
    'redditrepostsleuth.core.celery.admin_tasks.check_for_subreddit_config_update_task': {'queue': 'config_update_check'}

}

# TODO - I don't like this solution but had to do it to reduce dependancies per service
# It allows us to only import the tasks we need for a specific worker
if os.getenv('CELERY_IMPORTS', None):
    imports = tuple(os.getenv('CELERY_IMPORTS').split(','))