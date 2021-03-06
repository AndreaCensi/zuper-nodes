import cbor2


from .constants import *


class Sink:
    def __init__(self, of):
        self.of = of

    def write_topic_message(self, topic, data, timing):
        """ Can raise BrokenPipeError"""
        m = {}
        m[FIELD_COMPAT] = [CUR_PROTOCOL]
        m[FIELD_TOPIC] = topic
        m[FIELD_DATA] = data
        m[FIELD_TIMING] = timing
        self._write_raw(m)

    def write_control_message(self, code, data=None):
        """ Can raise BrokenPipeError"""
        m = {}
        m[FIELD_CONTROL] = code
        m[FIELD_DATA] = data
        self._write_raw(m)

    def _write_raw(self, m: dict):
        """ Can raise BrokenPipeError"""
        j = cbor2.dumps(m)
        self.of.write(j)
        self.of.flush()

