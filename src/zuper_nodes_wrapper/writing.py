import cbor2

from .constants import CUR_PROTOCOL
from .constants import FIELD_COMPAT
from .constants import FIELD_CONTROL
from .constants import FIELD_DATA
from .constants import FIELD_TIMING
from .constants import FIELD_TOPIC

__all__ = [
    "Sink",
]


class Sink:
    def __init__(self, of):
        self.of = of

    def write_topic_message(self, topic: str, data: object, timing):
        """Can raise BrokenPipeError"""
        m = {}
        m[FIELD_COMPAT] = [CUR_PROTOCOL]
        m[FIELD_TOPIC] = topic
        m[FIELD_DATA] = data
        m[FIELD_TIMING] = timing
        self._write_raw(m)

    def write_control_message(self, code, data: object = None):
        """Can raise BrokenPipeError"""
        m = {}
        m[FIELD_CONTROL] = code
        m[FIELD_DATA] = data
        self._write_raw(m)

    def _write_raw(self, m: dict):
        """Can raise BrokenPipeError"""
        j = cbor2.dumps(m)
        self.of.write(j)
        self.of.flush()
