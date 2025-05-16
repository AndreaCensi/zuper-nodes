from dataclasses import dataclass

from zuper_commons.text import indent

from .language import Either
from .language import ExpectInputReceived
from .language import ExpectOutputProduced
from .language import InputReceived
from .language import InSequence
from .language import Language
from .language import OneOrMore
from .language import OutputProduced
from .language import ZeroOrMore
from .language import ZeroOrOne
from .language import ZEvent

__all__ = [
    "Always",
    "Enough",
    "LanguageChecker",
    "NeedMore",
    "Unexpected",
]


class Result:
    pass


@dataclass
class Enough(Result):
    pass


@dataclass
class Unexpected(Result):
    msg: str

    def __repr__(self):
        return "Unexpected:" + indent(self.msg, "  ")


@dataclass
class NeedMore(Result):
    pass


import networkx as nx

NodeName = tuple[str, ...]


class Always:
    pass


def get_nfa(
    g: nx.DiGraph | None,
    start_node: NodeName,
    accept_node: NodeName,
    l: Language,
    prefix: tuple[str, ...] = (),
):
    # assert start_node != accept_node
    if not start_node in g:
        g.add_node(start_node, label="/".join(start_node))
    if not accept_node in g:
        g.add_node(accept_node, label="/".join(accept_node))
    if isinstance(l, ExpectOutputProduced):
        g.add_edge(start_node, accept_node, event_match=l, label=f"out/{l.channel}")
    elif isinstance(l, ExpectInputReceived):
        g.add_edge(start_node, accept_node, event_match=l, label=f"in/{l.channel}")
    elif isinstance(l, InSequence):
        current = start_node
        for i, li in enumerate(l.ls):
            # if i == len(l.ls) - 1:
            #     n = accept_node
            # else:
            n = prefix + (f"after{i}",)
            g.add_node(n)
            # logger.debug(f'sequence {i} start {current} to {n}')
            get_nfa(g, start_node=current, accept_node=n, prefix=prefix + (f"{i}",), l=li)
            current = n

        g.add_edge(current, accept_node, event_match=Always(), label="always")

    elif isinstance(l, ZeroOrMore):
        # logger.debug(f'zeroormore {start_node} -> {accept_node}')

        g.add_edge(start_node, accept_node, event_match=Always(), label="always")
        get_nfa(
            g,
            start_node=accept_node,
            accept_node=accept_node,
            l=l.l,
            prefix=prefix + ("zero_or_more",),
        )

    elif isinstance(l, OneOrMore):
        # start to accept
        get_nfa(
            g,
            start_node=start_node,
            accept_node=accept_node,
            l=l.l,
            prefix=prefix + ("one_or_more", "1"),
        )
        # accept to accept
        get_nfa(
            g,
            start_node=accept_node,
            accept_node=accept_node,
            l=l.l,
            prefix=prefix + ("one_or_more", "2"),
        )

    elif isinstance(l, ZeroOrOne):
        g.add_edge(start_node, accept_node, event_match=Always(), label="always")
        get_nfa(
            g,
            start_node=start_node,
            accept_node=accept_node,
            l=l.l,
            prefix=prefix + ("zero_or_one",),
        )

    elif isinstance(l, Either):
        for i, li in enumerate(l.ls):
            get_nfa(
                g,
                start_node=start_node,
                accept_node=accept_node,
                l=li,
                prefix=prefix + (f"either{i}",),
            )
    else:
        raise AssertionError(type(l))


def event_matches(l: Language, event: ZEvent):
    if isinstance(l, ExpectInputReceived):
        return isinstance(event, InputReceived) and event.channel == l.channel

    if isinstance(l, ExpectOutputProduced):
        return isinstance(event, OutputProduced) and event.channel == l.channel

    if isinstance(l, Always):
        return False
    raise NotImplementedError(l)


START = ("start",)
ACCEPT = ("accept",)


class LanguageChecker:
    g: nx.DiGraph
    active: set[NodeName]

    def __init__(self, language: Language):
        self.g = nx.MultiDiGraph()
        self.start_node = START
        self.accept_node = ACCEPT
        get_nfa(
            g=self.g,
            l=language,
            start_node=self.start_node,
            accept_node=self.accept_node,
            prefix=(),
        )
        # for (a, b, data) in self.g.out_edges(data=True):
        #     print(f'{a} -> {b} {data["event_match"]}')
        a = 2
        for n in self.g:
            if n not in [START, ACCEPT]:
                # noinspection PyUnresolvedReferences
                self.g.nodes[n]["label"] = f"S{a}"
                a += 1
            elif n == START:
                # noinspection PyUnresolvedReferences
                self.g.nodes[n]["label"] = "start"
            elif n == ACCEPT:
                # noinspection PyUnresolvedReferences
                self.g.nodes[n]["label"] = "accept"

        self.active = {self.start_node}
        # logger.debug(f'active {self.active}')
        self._evolve_empty()

    def _evolve_empty(self):
        while True:
            now_active = set()
            for node in self.active:
                nalways = 0
                nother = 0
                for _, neighbor, data in self.g.out_edges(nbunch=[node], data=True):
                    # print(f'-> {neighbor} {data["event_match"]}')
                    if isinstance(data["event_match"], Always):
                        now_active.add(neighbor)
                        nalways += 1
                    else:
                        nother += 1
                if nother or (nalways == 0):
                    now_active.add(node)

            if self.active == now_active:
                break
            self.active = now_active

    def push(self, event) -> Result:
        now_active = set()
        # print(f'push: active is {self.active}')
        # print(f'push: considering {event}')
        for node in self.active:
            for _, neighbor, data in self.g.out_edges(nbunch=[node], data=True):
                if event_matches(data["event_match"], event):
                    # print(f'now activating {neighbor}')
                    now_active.add(neighbor)
                # else:
                #     print(f"event_match {event} does not match {data['event_match']}")
        #
        # if not now_active:
        #     return Unexpected('')

        self.active = now_active
        # print(f'push: now active is {self.active}')
        self._evolve_empty()
        # print(f'push: now active is {self.active}')
        return self.finish()

    def finish(self) -> NeedMore | Enough | Unexpected:
        # print(f'finish: active is {self.active}')
        if not self.active:
            return Unexpected("no active")
        if self.accept_node in self.active:
            return Enough()
        return NeedMore()

    def get_active_states_names(self):
        return [self.g.nodes[_]["label"] for _ in self.active]

    def get_expected_events(self) -> set:
        events = set()
        for state in self.active:
            for _, neighbor, data in self.g.out_edges(nbunch=[state], data=True):
                em = data["event_match"]
                if not isinstance(em, Always):
                    events.add(em)
        return events
