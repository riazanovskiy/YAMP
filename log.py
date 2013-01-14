import logging

LOG_FORMAT = '(%(asctime)s)[%(levelname)s]: %(message)s'

logging.basicConfig(format=LOG_FORMAT, datefmt='%H:%M:%S')  # %m.%d.%Y

logger = logging.getLogger('yamp_logger')
logger.setLevel(logging.DEBUG)
