from dataclasses import dataclass
from typing import Generic
from typing import NewType
from typing import TypeVar

from zuper_nodes.structures import TimingInfo

from .constants import FIELD_CONTROL
from .constants import FIELD_DATA

X = TypeVar("X")


@dataclass
class MsgReceived(Generic[X]):
    topic: str
    data: X
    timing: TimingInfo


@dataclass
class RawTopicMessage:
    topic: str
    data: dict | None
    timing: dict | None


@dataclass
class ControlMessage:
    code: str
    msg: str | None


WireMessage = NewType("WireMessage", dict)


class Malformed(Exception):
    pass


def interpret_control_message(m: WireMessage) -> ControlMessage:
    if not isinstance(m, dict):
        msg = f"Expected dictionary, not {type(m)}."
        raise Malformed(msg)
    if not FIELD_CONTROL in m:
        msg = f"Expected field {FIELD_CONTROL}, obtained {list(m)}."
        raise Malformed(msg)
    code = m[FIELD_CONTROL]
    msg = m.get(FIELD_DATA, None)
    return ControlMessage(code, msg)
