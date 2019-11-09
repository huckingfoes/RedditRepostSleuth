# TODO - Mega hackery, figure this out.
import sys



sys.path.append('./')
from redditrepostsleuth.core.db.db_utils import get_db_engine
from redditrepostsleuth.core.services.eventlogging import EventLogging
from redditrepostsleuth.core.db.uow.sqlalchemyunitofworkmanager import SqlAlchemyUnitOfWorkManager
from redditrepostsleuth.core.responsebuilder import ResponseBuilder
from redditrepostsleuth.core.util.reddithelpers import get_reddit_instance
from redditrepostsleuth.core.logging import log
from redditrepostsleuth.core.duplicateimageservice import DuplicateImageService
from redditrepostsleuth.summonssvc.summonshandler import SummonsHandler



if __name__ == '__main__':
    uowm = SqlAlchemyUnitOfWorkManager(get_db_engine())
    dup = DuplicateImageService(uowm)
    response_builder = ResponseBuilder(uowm)
    summons = SummonsHandler(uowm, dup, get_reddit_instance(), response_builder, event_logger=EventLogging(), summons_disabled=False)

    while True:
        try:
            summons.handle_summons()
        except Exception as e:
            log.exception('Summons handler crashed', exc_info=True)





