import pyparsing
from pyparsing import Keyword
from pyparsing import Literal
from pyparsing import ParserElement
from pyparsing import Suppress
from pyparsing import opAssoc
from pyparsing import pyparsing_common

try:
    from pyparsing import operatorPrecedence
except ImportError:  # pragma: no cover
    from pyparsing import infixNotation as operatorPrecedence

from .language import Either
from .language import ExpectInputReceived
from .language import ExpectOutputProduced
from .language import InSequence
from .language import Language
from .language import OneOrMore
from .language import ZeroOrMore
from .language import ZeroOrOne

__all__ = [
    "Syntax",
    "language_to_str",
    "parse_language",
]

ParserElement.enablePackrat()

S = Suppress
L = Literal
K = Keyword


def parse_language(s: str) -> Language:
    try:
        res = Syntax.language.parseString(s, parseAll=True)
    except pyparsing.ParseException as e:
        msg = f"Cannot parse the language:\n\n{s}"
        raise Exception(msg) from e

    res = res[0]
    return res


def language_to_str(l: Language):
    def quote_if(s):
        if ";" in s or "|" in s:
            return "(" + s + ")"
        else:
            return s

    if isinstance(l, ExpectInputReceived):
        return f"in:{l.channel}"
    if isinstance(l, ExpectOutputProduced):
        return f"out:{l.channel}"
    if isinstance(l, InSequence):
        return " ; ".join(quote_if(language_to_str(_)) for _ in l.ls)
    if isinstance(l, Either):
        return " | ".join(quote_if(language_to_str(_)) for _ in l.ls)
    if isinstance(l, ZeroOrMore):
        return "(" + language_to_str(l.l) + ")" + "*"
    if isinstance(l, OneOrMore):
        return "(" + language_to_str(l.l) + ")" + "+"
    if isinstance(l, ZeroOrOne):
        return "(" + language_to_str(l.l) + ")" + "?"
    raise NotImplementedError(type(l))


def on_input_received(s, loc, tokens):
    return ExpectInputReceived(tokens[0])


def on_output_produced(s, loc, tokens):
    return ExpectOutputProduced(tokens[0])


def on_in_sequence(tokens):
    return InSequence(tuple(tokens[0]))


def on_either(tokens):
    return Either(tuple(tokens[0]))


def on_zero_or_one(tokens):
    return ZeroOrOne(tokens[0][0])


def on_zero_or_more(tokens):
    return ZeroOrMore(tokens[0][0])


def on_one_or_more(tokens):
    return OneOrMore(tokens[0][0])


class Syntax:
    input_received = S(K("in") + L(":")) + pyparsing_common.identifier
    output_produced = S(K("out") + L(":")) + pyparsing_common.identifier

    basic = input_received | output_produced

    language = operatorPrecedence(
        basic,
        [
            (S(L("*")), 1, opAssoc.LEFT, on_zero_or_more),
            (S(L("+")), 1, opAssoc.LEFT, on_one_or_more),
            (S(L("?")), 1, opAssoc.LEFT, on_zero_or_one),
            (S(L(";")), 2, opAssoc.LEFT, on_in_sequence),
            (S(L("|")), 2, opAssoc.LEFT, on_either),
        ],
    )

    input_received.setParseAction(on_input_received)
    output_produced.setParseAction(on_output_produced)
