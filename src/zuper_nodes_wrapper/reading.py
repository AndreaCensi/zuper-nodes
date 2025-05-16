import select
import time
from collections.abc import Iterator
from typing import Union

from zuper_commons.text import indent
from zuper_ipce import read_next_cbor

from zuper_nodes.structures import ExternalTimeout

from . import logger
from .constants import CUR_PROTOCOL
from .constants import FIELD_COMPAT
from .constants import FIELD_CONTROL
from .constants import FIELD_DATA
from .constants import FIELD_TIMING
from .constants import FIELD_TOPIC
from .struct import ControlMessage
from .struct import RawTopicMessage
from .struct import WireMessage
from .struct import interpret_control_message

M = Union[RawTopicMessage, ControlMessage]


def inputs(f, give_up: float | None = None, waiting_for: str | None = None) -> Iterator[M]:
    last = time.time()
    intermediate_timeout = 3.0
    intermediate_timeout_multiplier = 1.5
    while True:
        readyr, readyw, readyx = select.select([f], [], [f], intermediate_timeout)
        if readyr:
            try:
                parsed = read_next_cbor(f, waiting_for=waiting_for)
            except StopIteration:
                return

            if not isinstance(parsed, dict):
                msg = f"Expected a dictionary, obtained {parsed!r}"
                logger.error(msg)
                continue

            if FIELD_CONTROL in parsed:
                m = interpret_control_message(WireMessage(parsed))
                yield m
            elif FIELD_TOPIC in parsed:
                if not FIELD_COMPAT in parsed:
                    msg = f'Could not find field "compat" in structure "{parsed}".'
                    logger.error(msg)
                    continue

                l = parsed[FIELD_COMPAT]
                if not isinstance(l, list):
                    msg = f"Expected a list for compatibility value, found {l!r}"
                    logger.error(msg)
                    continue

                if not CUR_PROTOCOL in parsed[FIELD_COMPAT]:
                    msg = f"Skipping message because could not find {CUR_PROTOCOL} in {l}."
                    logger.warn(msg)
                    continue

                rtm = RawTopicMessage(
                    parsed[FIELD_TOPIC],
                    parsed.get(FIELD_DATA, None),
                    parsed.get(FIELD_TIMING, None),
                )
                yield rtm

        elif readyx:
            logger.warning(f"Exceptional condition on input channel {readyx}")
        else:
            delta = time.time() - last
            if give_up is not None and (delta > give_up):
                msg = f"I am giving up after {delta:.1f} seconds."
                raise ExternalTimeout(msg)
            else:
                intermediate_timeout *= intermediate_timeout_multiplier
                msg = f"Input channel not ready after {delta:.1f} seconds. Will re-try."
                if waiting_for:
                    msg += "\n" + indent(waiting_for, "> ")
                msg += f"\n I will warn again in {intermediate_timeout:.1f} seconds."
                logger.warning(msg)
