from zuper_commons.test_utils import my_assert_equal
from zuper_commons.types import check_isinstance

from zuper_nodes import ChannelName
from zuper_nodes import Either
from zuper_nodes import ExpectInputReceived
from zuper_nodes import ExpectOutputProduced
from zuper_nodes import InSequence
from zuper_nodes import Language
from zuper_nodes import OneOrMore
from zuper_nodes import ZeroOrMore
from zuper_nodes import ZeroOrOne
from zuper_nodes.language_parse import Syntax


def parse_language(s: str) -> Language:
    expr = Syntax.language
    res = expr.parseString(s, parseAll=True)
    res = res[0]
    return res


def expect_parse(expr, s, expected):
    check_isinstance(s, str)
    check_isinstance(expected, (type(None), Language))
    res = expr.parseString(s, parseAll=True)

    res = res[0]
    print(f"Obtained: {res}")
    print(f"Expected: {expected}")
    if expected:
        my_assert_equal(res, expected)


def test_parse_language_01() -> None:
    s = "in:name"
    e = ExpectInputReceived(ChannelName("name"))
    expect_parse(Syntax.input_received, s, e)
    expect_parse(Syntax.language, s, e)


def test_parse_language_02() -> None:
    s = "out:name"
    e = ExpectOutputProduced(ChannelName("name"))
    expect_parse(Syntax.output_produced, s, e)


def test_parse_language_03() -> None:
    s = "out:first ; in:second"
    e = InSequence((ExpectOutputProduced(ChannelName("first")), ExpectInputReceived(ChannelName("second"))))
    expect_parse(Syntax.language, s, e)


def test_parse_language_04() -> None:
    s = "(out:first)*"
    e = ZeroOrMore(ExpectOutputProduced(ChannelName("first")))
    expect_parse(Syntax.language, s, e)


def test_parse_language_05() -> None:
    s = "(out:first)?"
    e = ZeroOrOne(ExpectOutputProduced(ChannelName("first")))
    expect_parse(Syntax.language, s, e)


def test_parse_language_06() -> None:
    s = "(out:first)+"
    e = OneOrMore(ExpectOutputProduced(ChannelName("first")))
    expect_parse(Syntax.language, s, e)


def test_parse_language_07() -> None:
    s = "out:first | out:second"
    e = Either((ExpectOutputProduced(ChannelName("first")), ExpectOutputProduced(ChannelName("second"))))
    expect_parse(Syntax.language, s, e)

    s2 = "(out:first | out:second)"
    expect_parse(Syntax.language, s2, e)


def test_parse_language_08() -> None:
    s = """
                (
                    in:next_episode ; (
                        out:no_episodes |
                        (out:episode_start ;
                            (in:next_image ; (out:image | out:episode_end))*)
                    )
                )*
            """

    expect_parse(Syntax.language, s, None)


def test_parse_language_09() -> None:
    s = """
                (
                    in:next_episode ; (
                        out:no_episodes |
                        (out:episode_start ;
                            (in:next_image ; (out:image | out:episode_end))*)
                    )
                )*
            """

    language = parse_language(s)
    op1 = language.opposite()
    op2 = op1.opposite()
    assert op2 == language


#
# def test_parse_language_08():
#     s = """
#                 (
#                     in:next_episode ; (
#                         out:no_episodes |
#                         (out:episode_start ;
#                             (in:next_image ; (out:image | out:episode_end))*)
#                     )
#                 )*
#             """
#
#     expect_parse(Syntax.language, s, None)
