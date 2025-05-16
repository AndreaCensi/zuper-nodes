import os
import stat
import time
from io import BufferedReader

from zuper_commons.fs import make_sure_dir_exists

from zuper_nodes import NodeEnvironmentError

from . import logger
from . import logger_interaction


def wait_for_creation(fn: str, wait: float = 3.0):
    t0 = time.time()
    if os.path.exists(fn):
        # logger.info(f"Found {fn} right away.")
        return
    while not os.path.exists(fn):
        time.sleep(wait)
        dt = int(time.time() - t0)
        msg = f"Waiting for creation of {fn} since {dt} seconds."
        logger.info(msg)

    dt = int(time.time() - t0)
    logger.debug(f"Found {fn} after {dt} seconds waiting.")


def open_for_read(fin: str, timeout: float = None):
    t0 = time.time()
    # first open reader file in case somebody is waiting for it
    if os.path.exists(fin):
        logger_interaction.info(f"Found file {fin} right away")
    else:
        while not os.path.exists(fin):
            delta = time.time() - t0
            if timeout is not None and (delta > timeout):
                msg = f"The file {fin!r} was not created before {timeout:.1f} seconds. I give up."
                raise NodeEnvironmentError(msg)
            logger_interaction.info(f"waiting for file {fin} to be created since {int(delta)} seconds.")
            time.sleep(1)
        delta = time.time() - t0
        logger_interaction.info(f"Waited for file {fin} for a total of {int(delta)} seconds")

    logger_interaction.info(f"Opening input {fin} for reading.")
    fi = open(fin, "rb", buffering=0)
    # noinspection PyTypeChecker
    fi = BufferedReader(fi, buffer_size=1)
    return fi


def open_for_write(fout: str):
    if fout == "/dev/stdout":
        logger_interaction.info("Opening stdout for writing")
        return open("/dev/stdout", "wb", buffering=0)
    else:
        wants_fifo = fout.startswith("fifo:")
        fout = fout.replace("fifo:", "")

        logger_interaction.info(f"Opening output file {fout} (wants fifo: {wants_fifo})")

        if not os.path.exists(fout):
            if wants_fifo:
                make_sure_dir_exists(fout)
                os.mkfifo(fout)
                logger_interaction.info(f"Fifo {fout} created.")
        else:
            is_fifo = stat.S_ISFIFO(os.stat(fout).st_mode)
            if wants_fifo and not is_fifo:
                logger_interaction.info(f"Recreating {fout} as a fifo.")
                os.unlink(fout)
                os.mkfifo(fout)

        if wants_fifo:
            logger_interaction.info(f"Fifo {fout} created. Opening will block until a reader appears.")
            logger.info(f"Fifo {fout} created. I will block until a reader appears.")

        make_sure_dir_exists(fout)
        fo = open(fout, "wb", buffering=0)
        logger.info(f"Fifo reader appeared for {fout}.")

        if wants_fifo:
            logger_interaction.info(f"A reader has connected to my fifo {fout}")

        return fo
