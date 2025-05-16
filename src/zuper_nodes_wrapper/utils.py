import inspect

from zuper_commons.types import ZTypeError

from . import logger

__all__ = [
    "call_if_fun_exists",
]


def call_if_fun_exists(ob, fname, **kwargs):
    kwargs = dict(kwargs)
    if not hasattr(ob, fname):
        msg = f"Missing function {fname}() for {type(ob)}"
        logger.warning(msg)
        return
    f = getattr(ob, fname)
    a = inspect.getfullargspec(f)
    for k, v in dict(kwargs).items():
        if k not in a.args:
            kwargs.pop(k)
    try:
        f(**kwargs)
    except TypeError as e:
        msg = f"Cannot call function {f}."
        raise ZTypeError(msg, f=f, args=kwargs, argspec=a) from e
