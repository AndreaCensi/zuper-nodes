__version__ = '1.0.4aaa'

from .col_logging import logger

logger.info(f'zuper-nodes {__version__}')

from .language import *

from .language_parse import *
from .language_recognize import *

from .structures import  *
