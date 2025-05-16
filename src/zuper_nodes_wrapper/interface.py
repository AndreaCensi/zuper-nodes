import sys
from abc import ABC
from abc import abstractmethod

from zuper_nodes.structures import TimingInfo

__all__ = [
    "Context",
    "wrap_direct",
]


def wrap_direct(node, protocol, args: list[str] | None = None):
    if args is None:
        args = sys.argv[1:]

    from .wrapper import check_implementation
    from .wrapper import run_loop

    # if PYTHON_36 or PYTHON_37:
    #     monkeypatch_findCaller()
    check_implementation(node, protocol)
    run_loop(node, protocol, args)


class Context(ABC):
    @abstractmethod
    def write(
        self,
        topic: str,
        data: object,
        timing: TimingInfo = None,
        with_schema: bool = False,
    ):
        pass

    @abstractmethod
    def info(self, msg: str):
        pass

    @abstractmethod
    def debug(self, msg: str):
        pass

    @abstractmethod
    def warning(self, msg: str):
        pass

    @abstractmethod
    def error(self, msg: str):
        pass

    @abstractmethod
    def get_hostname(self):
        pass
