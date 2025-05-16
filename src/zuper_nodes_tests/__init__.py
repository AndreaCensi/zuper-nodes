from zuper_commons.logs import ZLogger
from zuper_commons.logs import ZLoggerInterface

logger: ZLoggerInterface = ZLogger(__name__)

from . import test_language
from . import test_protocol
