from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterator, Optional, Tuple

# Events

ChannelName = str


class Event:
    pass


@dataclass(frozen=True, unsafe_hash=True)
class InputReceived(Event):
    channel: ChannelName


@dataclass(frozen=True, unsafe_hash=True)
class OutputProduced(Event):
    channel: ChannelName


# Language over events

class Language(metaclass=ABCMeta):

    @abstractmethod
    def collect_simple_events(self) -> Iterator[Event]:
        pass


@dataclass(frozen=True, unsafe_hash=True)
class ExpectInputReceived(Language):
    channel: ChannelName

    def collect_simple_events(self):
        yield InputReceived(self.channel)


@dataclass(frozen=True, unsafe_hash=True)
class ExpectOutputProduced(Language):
    channel: ChannelName

    def collect_simple_events(self):
        yield OutputProduced(self.channel)


@dataclass(frozen=True, unsafe_hash=True)
class InSequence(Language):
    ls: Tuple[Language, ...]

    def collect_simple_events(self):
        for l in self.ls:
            yield from l.collect_simple_events()


@dataclass(frozen=True, unsafe_hash=True)
class ZeroOrOne(Language):
    l: Language

    def collect_simple_events(self):
        yield from self.l.collect_simple_events()


@dataclass(frozen=True, unsafe_hash=True)
class ZeroOrMore(Language):
    l: Language

    def collect_simple_events(self):
        yield from self.l.collect_simple_events()


@dataclass(frozen=True, unsafe_hash=True)
class OneOrMore(Language):
    l: Language

    def collect_simple_events(self):
        yield from self.l.collect_simple_events()


@dataclass(frozen=True, unsafe_hash=True)
class Either(Language):
    ls: Tuple[Language, ...]

    def collect_simple_events(self):
        for l in self.ls:
            yield from l.collect_simple_events()


# Interaction protocol


@dataclass
class InteractionProtocol:
    # Description
    description: str
    # Type for each input or output
    inputs: Dict[ChannelName, type]
    outputs: Dict[ChannelName, type]
    # The interaction language
    language: str

    # interaction: Language = None

    def __post_init__(self):
        from .language_parse import parse_language, language_to_str
        self.interaction = parse_language(self.language)

        simple_events = list(self.interaction.collect_simple_events())
        for e in simple_events:
            if isinstance(e, InputReceived):
                if e.channel not in self.inputs:
                    msg = f'Could not find input channel "{e.channel}" among {sorted(self.inputs)}.'
                    raise ValueError(msg)

            if isinstance(e, OutputProduced):
                if e.channel not in self.outputs:
                    msg = f'Could not find output channel "{e.channel}" among {sorted(self.outputs)}.'
                    raise ValueError(msg)

        self.language = language_to_str(self.interaction)


def particularize(ip: InteractionProtocol,
                  description: Optional[str] = None,
                  inputs: Optional[Dict[str, type]] = None,
                  outputs: Optional[Dict[str, type]] = None) -> InteractionProtocol:
    inputs2 = dict(ip.inputs)
    inputs2.update(inputs or {})
    outputs2 = dict(ip.outputs)
    outputs2.update(outputs or {})
    language = ip.language
    description = description or ip.description
    protocol2 = InteractionProtocol(description, inputs2, outputs2, language)

    from .compatibility import check_compatible_protocol
    check_compatible_protocol(protocol2, ip)
    return protocol2
