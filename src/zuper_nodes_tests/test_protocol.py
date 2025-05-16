import os
from collections.abc import Sequence

from networkx.drawing.nx_pydot import write_dot
from zuper_commons.fs import make_sure_dir_exists

from zuper_nodes import ChannelName
from zuper_nodes import InputReceived
from zuper_nodes import Language
from zuper_nodes import OutputProduced
from zuper_nodes import ZEvent
from zuper_nodes import logger
from zuper_nodes.language_parse import language_to_str
from zuper_nodes.language_parse import parse_language
from zuper_nodes.language_recognize import Enough
from zuper_nodes.language_recognize import LanguageChecker
from zuper_nodes.language_recognize import NeedMore
from zuper_nodes.language_recognize import Unexpected
from zuper_nodes_wrapper.meta_protocol import basic_protocol


def _fix():
    # this is needed because we import it implicitly using
    # from networkx.drawing.nx_pydot import write_dot
    import pydot

    _ = pydot


def assert_seq(s: str | Language, seq: list[ZEvent], expect: Sequence[type], final: type):
    if isinstance(s, str):
        s = s.replace("\n", " ").strip()
        while "  " in s:
            s = s.replace("  ", " ")
        l = parse_language(s)
    else:  # pragma: no cover
        l = s

    s2 = language_to_str(l)
    print(s)
    print(s2)
    l2 = parse_language(s2)
    assert l == l2, (s, s2)

    pc = LanguageChecker(l)
    logger.info(f"Active start: {pc.get_active_states_names()}")

    dn = "/tmp"
    fn = os.path.join(dn, "language.dot")
    make_sure_dir_exists(fn)
    write_dot(pc.g, fn)
    logger.info(f"Written to {fn}")

    # all except last
    for i, (e, r) in enumerate(zip(seq, expect)):
        logger.info(f"Active before: {pc.get_active_states_names()}")
        logger.info(f"Event {e}")
        res = pc.push(e)
        logger.info(f"Active after: {pc.get_active_states_names()}")
        if not isinstance(res, r):  # pragma: no cover
            msg = f"Input {i} ({e}) response was {type(res).__name__} instead of {r.__name__}"
            msg += f"\n entire sequence: {seq}"
            msg += f"\n language: {l}"
            msg += f"\n language string: {s2}"
            raise Exception(msg)

    res = pc.finish()
    if not isinstance(res, final):  # pragma: no cover
        msg = f"finish response was {type(res).__name__} instead of {final.__name__}"
        msg += f"\n entire sequence: {seq}"
        msg += f"\n language: {l}"
        msg += f"\n language string: {s2}"
        raise Exception(msg)


def test_proto_out1() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a", seq, (Enough,), Enough)


def test_proto_in1() -> None:
    seq = [InputReceived(ChannelName("a"))]
    assert_seq("in:a", seq, (Enough,), Enough)


def test_proto3() -> None:
    seq = [InputReceived(ChannelName("a"))]
    assert_seq("out:a", seq, (Unexpected,), Unexpected)


def test_proto4() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("in:a", seq, (Unexpected,), Unexpected)


def test_proto05() -> None:
    seq = [InputReceived(ChannelName("b"))]
    assert_seq("in:a", seq, (Unexpected,), Unexpected)


def test_proto06() -> None:
    seq = [OutputProduced(ChannelName("b"))]
    assert_seq("in:a", seq, (Unexpected,), Unexpected)


def test_proto07() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("b"))]
    assert_seq("out:a ; out:b", seq, (NeedMore, Enough), Enough)


def test_proto08() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("b"))]
    assert_seq("out:a ; out:b ; out:b", seq, (NeedMore, NeedMore), NeedMore)


def test_proto09() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a ; out:b", seq, (NeedMore,), NeedMore)


def test_proto10() -> None:
    seq = [
        OutputProduced(ChannelName("a")),
        OutputProduced(ChannelName("b")),
        OutputProduced(ChannelName("c")),
    ]
    assert_seq("out:a ; out:b", seq, (NeedMore, Enough, Unexpected), Unexpected)


def test_proto_zom_01() -> None:
    seq = []
    assert_seq("out:a *", seq, (), Enough)


def test_proto_zom_02() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a *", seq, (Enough,), Enough)


def test_proto_zom_03() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("a"))]
    assert_seq("out:a *", seq, (Enough, Enough), Enough)


def test_proto_either_01() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a | out:b ", seq, (Enough,), Enough)


def test_proto_either_02() -> None:
    seq = [OutputProduced(ChannelName("b"))]
    assert_seq("out:a | out:b ", seq, (Enough,), Enough)


def test_proto_either_03() -> None:
    seq = [OutputProduced(ChannelName("c"))]
    assert_seq("out:a | out:b | out:c ", seq, (Enough,), Enough)


def test_proto_either_04() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("b"))]
    assert_seq("(out:a ; out:b) | (out:b ; out:a) ", seq, (NeedMore, Enough), Enough)


def test_proto_either_05() -> None:
    seq = [OutputProduced(ChannelName("b")), OutputProduced(ChannelName("a"))]
    assert_seq(
        "(out:a ; out:b) | (out:b ; out:a) ",
        seq,
        (
            NeedMore,
            Enough,
        ),
        Enough,
    )


def test_proto_oom_01() -> None:
    seq = []
    assert_seq("out:a +", seq, (), NeedMore)


def test_proto_oom_02() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a +", seq, (Enough,), Enough)


def test_proto_oom_03() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("a"))]
    assert_seq("out:a +", seq, (Enough, Enough), Enough)


def test_proto_zoom_01() -> None:
    seq = []
    assert_seq("out:a ?", seq, (), Enough)


def test_proto_zoom_02() -> None:
    seq = [OutputProduced(ChannelName("a"))]
    assert_seq("out:a ?", seq, (Enough,), Enough)


def test_proto_zoom_03() -> None:
    seq = [OutputProduced(ChannelName("a")), OutputProduced(ChannelName("a"))]
    assert_seq("out:a ?", seq, (Enough, Unexpected), Unexpected)


def test_protocol_complex1() -> None:
    l = """
        (
            in:next_episode ; (
                out:no_more_episodes |
                (out:episode_start ;
                    (in:next_image ; (out:image | out:no_more_images))*)
            )
        )*
    """
    seq = [InputReceived(ChannelName("next_episode")), OutputProduced(ChannelName("episode_start"))]
    assert_seq(l, seq, (NeedMore, Enough), Enough)


def test_protocol_complex1_0() -> None:
    l = """

            in:next_episode ; (
                out:no_more_episodes |
                (out:episode_start ;
                    (in:next_image ; (out:image | out:no_more_images))*)
            )

    """
    seq = [InputReceived(ChannelName("next_episode")), OutputProduced(ChannelName("no_more_episodes"))]
    assert_seq(l, seq, (NeedMore, Enough), Enough)


def test_protocol_complex1_1() -> None:
    l = """

               in:next_episode ; (
                   out:no_more_episodes |
                   (out:episode_start ;
                       (in:next_image ; (out:image | out:no_more_images))*)
               )

       """
    seq = [InputReceived(ChannelName("next_episode")), OutputProduced(ChannelName("episode_start"))]
    assert_seq(l, seq, (NeedMore, Enough), Enough)


def test_protocol_complex1_2() -> None:
    l = """

               in:next_episode ; (
                   out:no_more_episodes |
                   (out:episode_start ;
                       (in:next_image ; (out:image | out:no_more_images))*)
               )

       """
    seq = [
        InputReceived(ChannelName("next_episode")),
        OutputProduced(ChannelName("episode_start")),
        InputReceived(ChannelName("next_image")),
        OutputProduced(ChannelName("image")),
    ]
    assert_seq(l, seq, (NeedMore, Enough), Enough)


def test_protocol_complex1_3() -> None:
    l = """
                (
                    in:next_episode ; (
                        out:no_more_episodes |
                        (out:episode_start ;
                            (in:next_image ; (out:image | out:no_more_images))*)
                    )
                )*
            """
    seq = [
        InputReceived(ChannelName("next_image")),
    ]
    assert_seq(l, seq, (Unexpected,), Unexpected)


def test_protocol_complex1_3b() -> None:
    l = """
                (
                    in:next_episode ; (
                        out:no_more_episodes |
                        (out:episode_start ;
                            (in:next_image ; (out:image | out:no_more_images))*)
                    )
                )*
            """
    seq = [
        InputReceived(ChannelName("next_image")),
    ]
    assert_seq(l, seq, (Unexpected,), Unexpected)


def test_protocol_complex1_3c() -> None:
    l = """
                (
                    in:next_episode ; (

                        (out:episode_start ;
                            (in:next_image)*)
                    )
                )*
            """
    seq = [
        InputReceived(ChannelName("next_image")),
    ]
    assert_seq(l, seq, (Unexpected,), Unexpected)


def test_protocol_complex1_3e() -> None:
    l = """
                (
                    in:next_episode ; (

                        (out:episode_start ;
                            (in:next_image)*)
                    )
                )
            """
    seq = [
        InputReceived(ChannelName("next_image")),
    ]
    assert_seq(l, seq, (Unexpected,), Unexpected)


def test_protocol_complex1_3d() -> None:
    l = """
                (
                    in:next_episode ; (

                        (out:episode_start ;
                            (in:next_image))
                    )
                )*
            """
    seq = [
        InputReceived(ChannelName("next_image")),
    ]
    assert_seq(l, seq, (Unexpected,), Unexpected)


def test_protocol_complex1_3v() -> None:
    l0 = """

        out:episode_start ;
            (in:next_image ; (out:image | out:no_more_images))*

        """
    seq = [OutputProduced(ChannelName("episode_start"))]
    assert_seq(l0, seq, (Enough,), Enough)


def test_basic_protocol1() -> None:
    l0 = basic_protocol.language
    seq = [InputReceived(ChannelName("set_config"))]
    assert_seq(l0, seq, (NeedMore,), NeedMore)
