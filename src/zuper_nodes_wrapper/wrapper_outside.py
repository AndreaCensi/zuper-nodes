import os
from io import BufferedReader
from typing import *

import cbor2 as cbor

from zuper_commons.text import indent
from zuper_json.ipce import object_to_ipce, ipce_to_object
from zuper_json.json2cbor import read_next_cbor
from zuper_nodes import InteractionProtocol, ExternalProtocolViolation
from zuper_nodes.compatibility import check_compatible_protocol
from zuper_nodes.structures import TimingInfo, RemoteNodeAborted, ExternalNodeDidNotUnderstand
from zuper_nodes_wrapper.meta_protocol import ProtocolDescription, basic_protocol
from zuper_nodes_wrapper.streams import wait_for_creation
from zuper_nodes_wrapper.struct import MsgReceived, interpret_control_message, WireMessage
from . import logger, logger_interaction
from .constants import *


class ComponentInterface:

    def __init__(self, fnin: str, fnout: str,
                 expect_protocol: InteractionProtocol, nickname: str):
        self.nickname = nickname
        self._cc = None
        try:
            os.mkfifo(fnin)
        except BaseException as e:
            msg = f'Cannot create fifo {fnin}'
            raise Exception(msg) from e
        self.fpin = open(fnin, 'wb', buffering=0)
        wait_for_creation(fnout)
        self.fnout = fnout
        f = open(fnout, 'rb', buffering=0)
        # noinspection PyTypeChecker
        self.fpout = BufferedReader(f, buffer_size=1)
        self.nreceived = 0
        self.expect_protocol = expect_protocol
        self.node_protocol = None
        self.data_protocol = None
        self.timeout = None

    def close(self):
        self.fpin.close()
        self.fpout.close()

    def cc(self, f):
        """ CC-s everything that is read or written to this file. """
        self._cc = f

    def _get_node_protocol(self, timeout=None):
        self.my_capabilities = {'z2': {CAPABILITY_PROTOCOL_REFLECTION: True}}
        msg = {FIELD_CONTROL: CTRL_CAPABILITIES,
               FIELD_DATA: self.my_capabilities}

        j = self._serialize(msg)
        self._write(j)

        msgs = read_reply(self.fpout, timeout=timeout, waiting_for=f"Reading {self.nickname} capabilities",
                          nickname=self.nickname)
        self.node_capabilities = msgs[0]['data']
        logger.info('My capabilities: %s' % self.my_capabilities)
        logger.info('Found capabilities: %s' % self.node_capabilities)
        if 'z2' not in self.node_capabilities:
            msg = 'Incompatible node; capabilities %s' % self.node_capabilities
            raise ExternalProtocolViolation(msg)

        z = self.node_capabilities['z2']
        if not z.get(CAPABILITY_PROTOCOL_REFLECTION, False):
            logger.info('Node does not support reflection.')
            if self.expect_protocol is None:
                msg = 'Node does not support reflection - need to provide protocol.'
                raise Exception(msg)
        else:

            ob: MsgReceived[ProtocolDescription] = \
                self.write_topic_and_expect('wrapper.describe_protocol',
                                            expect='protocol_description',
                                            timeout=timeout)
            self.node_protocol = ob.data.data
            self.data_protocol = ob.data.meta

            if self.expect_protocol is not None:
                check_compatible_protocol(self.node_protocol, self.expect_protocol)

    def write_topic_and_expect(self, topic, data=None, with_schema=False,
                               timeout=None,
                               timing=None,
                               expect=None) -> MsgReceived:
        timeout = timeout or self.timeout
        self._write_topic(topic, data=data, with_schema=with_schema, timing=timing)
        ob: MsgReceived = self.read_one(expect_topic=expect, timeout=timeout)
        return ob

    def write_topic_and_expect_zero(self, topic, data=None, with_schema=False,
                                    timeout=None,
                                    timing=None):
        timeout = timeout or self.timeout
        self._write_topic(topic, data=data, with_schema=with_schema, timing=timing)
        msgs = read_reply(self.fpout, timeout=timeout,
                          nickname=self.nickname)
        if msgs:
            msg = 'Expecting zero, got %s' % msgs
            raise ExternalProtocolViolation(msg)

    def _write_topic(self, topic, data=None, with_schema=False, timing=None):
        suggest_type = None
        if self.node_protocol:
            if topic in self.node_protocol.inputs:
                suggest_type = self.node_protocol.inputs[topic]

        ipce = object_to_ipce(data,
                              {},
                              with_schema=with_schema,
                              suggest_type=suggest_type)

        # try to re-read
        if suggest_type:
            try:
                _ = ipce_to_object(ipce, {}, expect_type=suggest_type)
            except BaseException as e:
                msg = f'While attempting to write on topic "{topic}", cannot ' \
                    f'interpret the value as {suggest_type}.\nValue: {data}'
                raise Exception(msg) from e  # XXX

        msg = {FIELD_COMPAT: [CUR_PROTOCOL],
               FIELD_TOPIC: topic,
               FIELD_DATA: ipce,
               FIELD_TIMING: timing}
        j = self._serialize(msg)
        self._write(j)
        # make sure we write the schema when we copy it
        if not with_schema:
            msg[FIELD_DATA] = object_to_ipce(data, {}, with_schema=True)
            j = self._serialize(msg)

        if self._cc:
            self._cc.write(j)
            self._cc.flush()

        logger_interaction.info(f'Written to topic "{topic}" >> {self.nickname}.')

    def _write(self, j):

        try:
            self.fpin.write(j)
            self.fpin.flush()
        except BrokenPipeError as e:
            msg = f'While attempting to write to node "{self.nickname}", ' \
                f'I reckon that the pipe is closed and the node exited.'
            try:
                received = self.read_one(expect_topic=TOPIC_ABORTED)
                if received.topic == TOPIC_ABORTED:
                    msg += '\n\nThis is the aborted message:'
                    msg += '\n\n' + indent(received.data, ' |')
            except BaseException as e2:
                msg += f'\n\nI could not read any aborted message: {e2}'
            raise RemoteNodeAborted(msg) from e

    def _serialize(self, msg) -> bytes:
        j = cbor.dumps(msg)
        return j

    def read_one(self, expect_topic=None, timeout=None) -> MsgReceived:
        timeout = timeout or self.timeout
        try:
            if expect_topic:
                waiting_for = f'Expecting topic "{expect_topic}" << {self.nickname}.'
            else:
                waiting_for = None

            msgs = read_reply(self.fpout, timeout=timeout, waiting_for=waiting_for,
                              nickname=self.nickname)

            if len(msgs) == 0:
                msg = f'Expected one message from node "{self.nickname}". Got zero.'
                if expect_topic:
                    msg += f'\nExpecting topic "{expect_topic}".'
                raise ExternalProtocolViolation(msg)
            if len(msgs) > 1:
                msg = f'Expected only one message. Got {msgs}'
                raise ExternalProtocolViolation(msg)
            msg = msgs[0]

            if FIELD_TOPIC not in msg:
                m = f'Invalid message does not contain the field "{FIELD_TOPIC}".'
                m += f'\n {msg}'
                raise ExternalProtocolViolation(m)
            topic = msg[FIELD_TOPIC]

            if expect_topic:
                if topic != expect_topic:
                    msg = f'I expected topic "{expect_topic}" but received "{topic}".'
                    raise ExternalProtocolViolation(msg)
            if topic in basic_protocol.outputs:
                klass = basic_protocol.outputs[topic]
            else:
                if self.node_protocol:
                    if topic not in self.node_protocol.outputs:
                        msg = f'Cannot find topic "{topic}" in outputs of detected node protocol.'
                        msg += '\nI know: %s' % sorted(self.node_protocol.outputs)
                        raise ExternalProtocolViolation(msg)
                    else:
                        klass = self.node_protocol.outputs[topic]
                else:
                    if not topic in self.expect_protocol.outputs:
                        msg = f'Cannot find topic "{topic}".'
                        raise ExternalProtocolViolation(msg)
                    else:
                        klass = self.expect_protocol.outputs[topic]
            data = ipce_to_object(msg[FIELD_DATA], {}, expect_type=klass)

            if self._cc:
                msg[FIELD_DATA] = object_to_ipce(data, {}, with_schema=True)
                msg_b = self._serialize(msg)
                self._cc.write(msg_b)
                self._cc.flush()

            if FIELD_TIMING not in msg:
                timing = TimingInfo()
            else:
                timing = ipce_to_object(msg[FIELD_TIMING], {}, expect_type=TimingInfo)
            self.nreceived += 1
            return MsgReceived[klass](topic, data, timing)

        except StopIteration as e:
            msg = 'EOF detected on %s after %d messages.' % (self.fnout, self.nreceived)
            if expect_topic:
                msg += f' Expected topic "{expect_topic}".'
            raise StopIteration(msg) from e
        except TimeoutError as e:
            msg = 'Timeout detected on %s after %d messages.' % (self.fnout, self.nreceived)
            if expect_topic:
                msg += f' Expected topic "{expect_topic}".'
            raise TimeoutError(msg) from e


def read_reply(fpout, nickname: str, timeout=None, waiting_for=None, ) -> List:
    """ Reads a control message. Returns if it is CTRL_UNDERSTOOD.
     Raises:
         TimeoutError
         RemoteNodeAborted
         ExternalNodeDidNotUnderstand
         ExternalProtocolViolation otherwise. """
    try:
        wm: WireMessage = read_next_cbor(fpout, timeout=timeout, waiting_for=waiting_for)
        # logger.debug(f'{nickname} sent {wm}')
    except StopIteration:
        msg = 'Remote node closed communication (%s)' % waiting_for
        raise RemoteNodeAborted(msg) from None

    cm = interpret_control_message(wm)
    if cm.code == CTRL_UNDERSTOOD:
        others = read_until_over(fpout, timeout=timeout, nickname=nickname)
        return others
    elif cm.code == CTRL_ABORTED:
        msg = f'The remote node "{nickname}" aborted with the following error:'
        msg += '\n\n' + indent(cm.msg, "|", f"error in {nickname} |")
        # others = self.read_until_over()
        raise RemoteNodeAborted(msg)
    elif cm.code == CTRL_NOT_UNDERSTOOD:
        _others = read_until_over(fpout, timeout=timeout, nickname=nickname)
        msg = f'The remote node "{nickname}" reports that it did not understand the message:'
        msg += '\n\n' + indent(cm.msg, "|", f"reported by {nickname} |")
        raise ExternalNodeDidNotUnderstand(msg)
    else:
        msg = 'Remote node raised unknown code %s: %s' % (cm, cm.code)
        raise ExternalProtocolViolation(msg)


def read_until_over(fpout, timeout, nickname) -> List[WireMessage]:
    """ Raises RemoteNodeAborted, TimeoutError """
    res = []
    waiting_for = f'Reading reply of {nickname}.'
    while True:
        try:
            wm: WireMessage = read_next_cbor(fpout, timeout=timeout, waiting_for=waiting_for)
            if wm.get(FIELD_CONTROL, '') == CTRL_ABORTED:
                m = f'External node "{nickname}" aborted:'
                m += '\n\n' + indent(wm.get(FIELD_DATA, None), "|",
                                     f"error in {nickname} |")
                raise RemoteNodeAborted(m)
            if wm.get(FIELD_CONTROL, '') == CTRL_OVER:
                # logger.info(f'Node "{nickname}" concluded output of %s messages.' % len(res))
                break
            # logger.info(f'Node "{nickname}" sent %s.' % len(wm))
        except StopIteration:
            msg = f'External node "{nickname}" closed communication.'
            raise RemoteNodeAborted(msg) from None
        except TimeoutError:
            msg = f'Timeout while reading output of node "{nickname}".'
            raise TimeoutError(msg) from None
        res.append(wm)
    return res
