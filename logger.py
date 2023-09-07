import logging
import sys

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    filename='program.log',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
