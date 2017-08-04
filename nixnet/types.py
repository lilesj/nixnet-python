from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import abc
import collections
import typing  # NOQA: F401

import six

from nixnet import _cconsts
from nixnet import _errors
from nixnet import _py2
from nixnet import constants

__all__ = [
    'DriverVersion',
    'CanComm',
    'CanIdentifier',
    'FrameFactory',
    'Frame',
    'RawFrame',
    'CanFrame']


DriverVersion = collections.namedtuple(
    'DriverVersion',
    ['major', 'minor', 'update', 'phase', 'build'])


CanComm_ = collections.namedtuple(
    'CanComm_',
    ['state', 'tcvr_err', 'sleep', 'last_err', 'tx_err_count', 'rx_err_count'])


class CanComm(CanComm_):
    """CAN Communication State.

    Attributes:
        state (:any:`nixnet._enums.CanCommState`): Communication State
        tcvr_err (bool): Transceiver Error.
            Transceiver error indicates whether an error condition exists on
            the physical transceiver. This is typically referred to as the
            transceiver chip NERR pin.  False indicates normal operation (no
            error), and true indicates an error.
        sleep (bool): Sleep.
            Sleep indicates whether the transceiver and communication
            controller are in their sleep state. False indicates normal
            operation (awake), and true indicates sleep.
        last_err (:any:`nixnet._enums.CanLastErr`): Last Error.
            Last error specifies the status of the last attempt to receive or
            transmit a frame
        tx_err_count (int): Transmit Error Counter.
            The transmit error counter begins at 0 when communication starts on
            the CAN interface. The counter increments when an error is detected
            for a transmitted frame and decrements when a frame transmits
            successfully. The counter increases more for an error than it is
            decreased for success. This ensures that the counter generally
            increases when a certain ratio of frames (roughly 1/8) encounter
            errors.
            When communication state transitions to Bus Off, the transmit error
            counter no longer is valid.
        rx_err_count (int): Receive Error Counter.
            The receive error counter begins at 0 when communication starts on
            the CAN interface. The counter increments when an error is detected
            for a received frame and decrements when a frame is received
            successfully. The counter increases more for an error than it is
            decreased for success. This ensures that the counter generally
            increases when a certain ratio of frames (roughly 1/8) encounter
            errors.
    """

    pass


class CanIdentifier(object):
    """CAN frame arbitration identifier.

    Attributes:
        identifier(int): CAN frame arbitration identifier
        extended(bool): If the identifier is extended
    """

    _FRAME_ID_MASK = 0x000003FF
    _EXTENDED_FRAME_ID_MASK = 0x1FFFFFFF

    def __init__(self, identifier, extended=False):
        # type: (int, bool) -> None
        self.identifier = identifier
        self.extended = extended

    @classmethod
    def from_raw(cls, raw):
        # type: (int) -> CanIdentifier
        """Parse a raw frame identifier into a CanIdentifier

        Args:
            raw(int): A raw frame identifier

        Returns:
            CanIdentifier: parsed value

        >>> CanIdentifier.from_raw(0x1)
        CanIdentifier(0x1)
        >>> CanIdentifier.from_raw(0x20000001)
        CanIdentifier(0x1, extended=True)
        """
        extended = bool(raw & _cconsts.NX_FRAME_ID_CAN_IS_EXTENDED)
        if extended:
            identifier = raw & cls._EXTENDED_FRAME_ID_MASK
        else:
            identifier = raw & cls._FRAME_ID_MASK
        return cls(identifier, extended)

    def __int__(self):
        """Convert CanIdentifier into a raw frame identifier

        >>> hex(int(CanIdentifier(1)))
        '0x1'
        >>> hex(int(CanIdentifier(1, True)))
        '0x20000001'
        """
        identifier = self.identifier
        if self.extended:
            if identifier != (identifier & self._EXTENDED_FRAME_ID_MASK):
                _errors.check_for_error(_cconsts.NX_ERR_UNDEFINED_FRAME_ID)
            identifier |= _cconsts.NX_FRAME_ID_CAN_IS_EXTENDED
        else:
            if identifier != (identifier & self._FRAME_ID_MASK):
                _errors.check_for_error(_cconsts.NX_ERR_UNDEFINED_FRAME_ID)
        return identifier

    def __eq__(self, other):
        if isinstance(other, CanIdentifier):
            other_id = typing.cast(CanIdentifier, other)
            return all((
                self.identifier == other_id.identifier,
                self.extended == other_id.extended))
        else:
            return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        else:
            return not result

    def __repr__(self):
        """CanIdentifier debug representation.

        >>> CanIdentifier(1)
        CanIdentifier(0x1)
        >>> CanIdentifier(1, True)
        CanIdentifier(0x1, extended=True)
        """
        if self.extended:
            return "CanIdentifier(0x{:x}, extended={})".format(
                self.identifier,
                self.extended)
        else:
            return "CanIdentifier(0x{:x})".format(
                self.identifier)


@six.add_metaclass(abc.ABCMeta)
class FrameFactory(object):
    """ABC for creating :any:`nixnet.types.Frame` objects."""

    __slots__ = ()

    @_py2.abstractclassmethod
    def from_raw(cls, frame):  # NOQA: N805 can't detect abstractclassmethod
        # No type annotation because mypy doesn't understand
        # abstractclassmethod is the same as classmethod
        """Convert from RawFrame."""
        pass


@six.add_metaclass(abc.ABCMeta)
class Frame(FrameFactory):
    """ABC for frame objects."""

    __slots__ = ()

    @abc.abstractmethod
    def to_raw(self):
        # type: () -> RawFrame
        """Convert to RawFrame."""
        pass

    @abc.abstractproperty
    def type(self):
        # type: () -> constants.FrameType
        """:any:`nixnet._enums.FrameType`: Frame format."""
        pass

    @abc.abstractmethod
    def __eq__(self, other):
        pass

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        else:
            return not result

    @abc.abstractmethod
    def __repr__(self):
        pass


class RawFrame(Frame):
    """Raw Frame.

    Attributes:
        timestamp(int): Absolute time the XNET interface received the end-of-frame.
        identifier(int): Frame identifier.
        type(:any:`nixnet._enums.FrameType`): Frame type.
        flags(int): Flags that qualify the type.
        info(int): Info that qualify the type.
        payload(bytes): Payload.
    """

    __slots__ = [
        "timestamp",
        "identifier",
        "_type",
        "flags",
        "info",
        "payload"]

    def __init__(self, timestamp, identifier, type, flags=0, info=0, payload=b""):
        # type: (int, int, constants.FrameType, int, int, bytes) -> None
        self.timestamp = timestamp
        self.identifier = identifier
        self._type = type
        self.flags = flags
        self.info = info
        self.payload = payload

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame."""
        return frame

    def to_raw(self):
        """Convert to RawFrame."""
        return self

    @property
    def type(self):
        return self._type

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(RawFrame, other)
            return all((
                self.timestamp == other_frame.timestamp,
                self.identifier == other_frame.identifier,
                self.type == other_frame.type,
                self.flags == other_frame.flags,
                self.info == other_frame.info,
                self.payload == other_frame.payload))
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """RawFrame debug representation.

        >>> RawFrame(1, 2, constants.FrameType.CAN_DATA, 3, 4)
        RawFrame(timestamp=0x1, identifier=0x2, type=FrameType.CAN_DATA, flags=0x3, info=0x4, payload=...)
        """
        return "RawFrame(timestamp=0x{:x}, identifier=0x{:x}, type={}, flags=0x{:x}, info=0x{:x}, payload=...)".format(
            self.timestamp,
            self.identifier,
            self.type,
            self.flags,
            self.info)


class CanFrame(Frame):
    """CAN Frame.

    Attributes:
        identifier(:any:`nixnet.types.CanIdentifier`): CAN frame arbitration identifier.
        echo(bool): If the frame is an echo of a successful
            transmit rather than being received from the network.
        type(:any:`nixnet._enums.FrameType`): Frame type.
        timestamp(int): Absolute time the XNET interface received the end-of-frame.
        payload(bytes): Payload.
    """

    __slots__ = [
        "identifier",
        "echo",
        "_type",
        "timestamp",
        "payload"]

    def __init__(self, identifier, type=constants.FrameType.CAN_DATA, payload=b""):
        # type: (typing.Union[CanIdentifier, int], constants.FrameType, bytes) -> None
        if isinstance(identifier, int):
            self.identifier = CanIdentifier(identifier)
        else:
            self.identifier = identifier
        self.echo = False  # Used only for Read
        self._type = type
        self.timestamp = 0  # Used only for Read
        self.payload = payload

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame.

        >>> raw = RawFrame(5, 0x20000001, constants.FrameType.CAN_DATA, _cconsts.NX_FRAME_FLAGS_TRANSMIT_ECHO, 0, b'')
        >>> CanFrame.from_raw(raw)
        CanFrame(CanIdentifier(0x1, extended=True), echo=True, type=FrameType.CAN_DATA, timestamp=0x5, payload=...)
        """
        identifier = CanIdentifier.from_raw(frame.identifier)
        can_frame = CanFrame(identifier, constants.FrameType(frame.type), frame.payload)
        can_frame.timestamp = frame.timestamp
        can_frame.echo = bool(frame.flags & _cconsts.NX_FRAME_FLAGS_TRANSMIT_ECHO)
        return can_frame

    def to_raw(self):
        """Convert to RawFrame.

        >>> CanFrame(CanIdentifier(1, True), constants.FrameType.CAN_DATA).to_raw()
        RawFrame(timestamp=0x0, identifier=0x20000001, type=FrameType.CAN_DATA, flags=0x0, info=0x0, payload=...)
        >>> c = CanFrame(CanIdentifier(1, True), constants.FrameType.CAN_DATA)
        >>> c.echo = True
        >>> c.to_raw()
        RawFrame(timestamp=0x0, identifier=0x20000001, type=FrameType.CAN_DATA, flags=0x80, info=0x0, payload=...)
        """
        identifier = int(self.identifier)
        flags = 0
        if self.echo:
            flags |= _cconsts.NX_FRAME_FLAGS_TRANSMIT_ECHO
        return RawFrame(self.timestamp, identifier, self.type, flags, 0, self.payload)

    @property
    def type(self):
        return self._type

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(CanFrame, other)
            return all((
                self.identifier == other_frame.identifier,
                self.echo == other_frame.echo,
                self.type == other_frame.type,
                self.timestamp == other_frame.timestamp,
                self.payload == other_frame.payload))
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """CanFrame debug representation.

        >>> CanFrame(1, constants.FrameType.CAN_DATA)
        CanFrame(CanIdentifier(0x1), echo=False, type=FrameType.CAN_DATA, timestamp=0x0, payload=...)
        """
        return "CanFrame({}, echo={}, type={}, timestamp=0x{:x}, payload=...)".format(
            self.identifier,
            self.echo,
            self.type,
            self.timestamp)


class CanBusErrorFrame(Frame):
    """Error detected on hardware bus of a :any:`nixnet.session.FrameInStreamSession`.

    .. note:: This requires enabling
       :any:`nixnet._session.intf.Interface.bus_err_to_in_strm`.

    Attributes:
        timestamp(int): Absolute time when the bus error occurred.
        state (:any:`nixnet._enums.CanCommState`): Communication State
        tcvr_err (bool): Transceiver Error.
        bus_err (:any:`nixnet._enums.CanLastErr`): Last Error.
        tx_err_count (int): Transmit Error Counter.
        rx_err_count (int): Receive Error Counter.
    """

    __slots__ = [
        "timestamp",
        "state",
        "tcvr_err",
        "bus_err",
        "tx_err_count",
        "rx_err_count"]

    def __init__(self, timestamp, state, tcvr_err, bus_err, tx_err_count, rx_err_count):
        # type: (int, constants.CanCommState, bool, constants.CanLastErr, int, int) -> None
        self.timestamp = timestamp
        self.state = state
        self.tcvr_err = tcvr_err
        self.bus_err = bus_err
        self.tx_err_count = tx_err_count
        self.rx_err_count = rx_err_count

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame.

        >>> raw = RawFrame(0x64, 0x0, constants.FrameType.CAN_BUS_ERROR, 0, 0, b'\\x00\\x01\\x02\\x03\\x04')
        >>> CanBusErrorFrame.from_raw(raw)
        CanBusErrorFrame(0x64, CanCommState.ERROR_ACTIVE, True, CanLastErr.STUFF, 3, 4)
        """
        timestamp = frame.timestamp
        state = constants.CanCommState(six.indexbytes(frame.payload, 0))
        tcvr_err = six.indexbytes(frame.payload, 1) != 0
        bus_err = constants.CanLastErr(six.indexbytes(frame.payload, 1))
        tx_err_count = six.indexbytes(frame.payload, 3)
        rx_err_count = six.indexbytes(frame.payload, 4)
        return CanBusErrorFrame(timestamp, state, tcvr_err, bus_err, tx_err_count, rx_err_count)

    def to_raw(self):
        """Convert to RawFrame.

        >>> CanBusErrorFrame(100, constants.CanCommState.BUS_OFF, True, constants.CanLastErr.STUFF, 1, 2).to_raw()
        RawFrame(timestamp=0x64, identifier=0x0, type=FrameType.CAN_BUS_ERROR, flags=0x0, info=0x0, payload=...)
        """
        identifier = 0
        flags = 0
        info = 0

        payload_data = [
            self.state.value,
            1 if self.tcvr_err else 0,
            self.bus_err.value,
            self.tx_err_count,
            self.rx_err_count,
        ]
        payload = bytes(payload_data)
        return RawFrame(self.timestamp, identifier, self.type, flags, info, payload)

    @property
    def type(self):
        return constants.FrameType.CAN_BUS_ERROR

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(CanBusErrorFrame, other)
            return all((
                self.timestamp == other_frame.timestamp,
                self.state == other_frame.state,
                self.tcvr_err == other_frame.tcvr_err,
                self.bus_err == other_frame.bus_err,
                self.tx_err_count == other_frame.tx_err_count,
                self.rx_err_count == other_frame.rx_err_count))
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """CanBusErrorFrame debug representation.

        >>> CanBusErrorFrame(100, constants.CanCommState.BUS_OFF, True, constants.CanLastErr.STUFF, 1, 2)
        CanBusErrorFrame(0x64, CanCommState.BUS_OFF, True, CanLastErr.STUFF, 1, 2)
        """
        return "CanBusErrorFrame(0x{:x}, {}, {}, {}, {}, {})".format(
            self.timestamp,
            self.state,
            self.tcvr_err,
            self.bus_err,
            self.tx_err_count,
            self.rx_err_count)


class DelayFrame(Frame):
    """Delay hardware when DelayFrame is outputted.

    .. note:: This requires
       :any:`nixnet._session.intf.Interface.out_strm_timng` to be in replay mode.

    Attributes:
        offset(int): Time to delay in milliseconds.
    """

    __slots__ = [
        "offset"]

    def __init__(self, offset):
        # type: (int) -> None
        self.offset = offset

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame.

        >>> raw = RawFrame(5, 0, constants.FrameType.SPECIAL_DELAY, 0, 0, b'')
        >>> DelayFrame.from_raw(raw)
        DelayFrame(5)
        """
        return DelayFrame(frame.timestamp)

    def to_raw(self):
        """Convert to RawFrame.

        >>> DelayFrame(250).to_raw()
        RawFrame(timestamp=0xfa, identifier=0x0, type=FrameType.SPECIAL_DELAY, flags=0x0, info=0x0, payload=...)
        """
        identifier = 0
        flags = 0
        info = 0
        payload = b''
        return RawFrame(self.offset, identifier, self.type, flags, info, payload)

    @property
    def type(self):
        return constants.FrameType.SPECIAL_DELAY

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(DelayFrame, other)
            return self.offset == other_frame.offset
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """DelayFrame debug representation.

        >>> DelayFrame(250)
        DelayFrame(250)
        """
        return "DelayFrame({})".format(self.offset)


class LogTriggerFrame(Frame):
    """Timestamp of when a trigger occurred.

    This frame is generated on input sessions when a rising edge is detected on
    an external connection.

    .. note:: This requires using
       :any:`nixnet._session.base.SessionBase.connect_terminals` to connect an
       external connection to the internal ``LogTrigger`` terminal.

    Attributes:
        timestamp(int): Absolute time that the trigger occurred.
    """

    __slots__ = [
        "timestamp"]

    def __init__(self, timestamp):
        # type: (int) -> None
        self.timestamp = timestamp

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame.

        >>> raw = RawFrame(5, 0, constants.FrameType.SPECIAL_LOG_TRIGGER, 0, 0, b'')
        >>> LogTriggerFrame.from_raw(raw)
        LogTriggerFrame(0x5)
        """
        return LogTriggerFrame(frame.timestamp)

    def to_raw(self):
        """Convert to RawFrame.

        >>> LogTriggerFrame(250).to_raw()
        RawFrame(timestamp=0xfa, identifier=0x0, type=FrameType.SPECIAL_LOG_TRIGGER, flags=0x0, info=0x0, payload=...)
        """
        identifier = 0
        flags = 0
        info = 0
        payload = b''
        return RawFrame(self.timestamp, identifier, self.type, flags, info, payload)

    @property
    def type(self):
        return constants.FrameType.SPECIAL_LOG_TRIGGER

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(LogTriggerFrame, other)
            return self.timestamp == other_frame.timestamp
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """LogTriggerFrame debug representation.

        >>> LogTriggerFrame(250)
        LogTriggerFrame(0xfa)
        """
        return "LogTriggerFrame(0x{:x})".format(self.timestamp)


class StartTriggerFrame(Frame):
    """Timestamp of :any:`nixnet.session.FrameInStreamSession` start.

    .. note:: This requires enabling
       :any:`nixnet._session.intf.Interface.start_trig_to_in_strm`.

    Attributes:
        timestamp(int): Absolute time that the trigger occurred.
    """

    __slots__ = [
        "timestamp"]

    def __init__(self, timestamp):
        # type: (int) -> None
        self.timestamp = timestamp

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame.

        >>> raw = RawFrame(5, 0, constants.FrameType.SPECIAL_START_TRIGGER, 0, 0, b'')
        >>> StartTriggerFrame.from_raw(raw)
        StartTriggerFrame(0x5)
        """
        return StartTriggerFrame(frame.timestamp)

    def to_raw(self):
        """Convert to RawFrame.

        >>> StartTriggerFrame(250).to_raw()
        RawFrame(timestamp=0xfa, identifier=0x0, type=FrameType.SPECIAL_START_TRIGGER, flags=0x0, info=0x0, payload=...)
        """
        identifier = 0
        flags = 0
        info = 0
        payload = b''
        return RawFrame(self.timestamp, identifier, self.type, flags, info, payload)

    @property
    def type(self):
        return constants.FrameType.SPECIAL_START_TRIGGER

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            other_frame = typing.cast(StartTriggerFrame, other)
            return self.timestamp == other_frame.timestamp
        else:
            return NotImplemented

    def __repr__(self):
        # type: () -> typing.Text
        """StartTriggerFrame debug representation.

        >>> StartTriggerFrame(250)
        StartTriggerFrame(0xfa)
        """
        return "StartTriggerFrame(0x{:x})".format(self.timestamp)


class XnetFrame(FrameFactory):
    """Create `Frame` based on `RawFrame` content."""

    __slots__ = ()

    @classmethod
    def from_raw(cls, frame):
        """Convert from RawFrame."""
        frame_type = {
            constants.FrameType.CAN_DATA: CanFrame,
            constants.FrameType.CAN20_DATA: CanFrame,
            constants.FrameType.CANFD_DATA: CanFrame,
            constants.FrameType.CANFDBRS_DATA: CanFrame,
            constants.FrameType.CAN_REMOTE: CanFrame,
            constants.FrameType.CAN_BUS_ERROR: CanBusErrorFrame,
            constants.FrameType.SPECIAL_DELAY: DelayFrame,
            constants.FrameType.SPECIAL_LOG_TRIGGER: LogTriggerFrame,
            constants.FrameType.SPECIAL_START_TRIGGER: StartTriggerFrame,
        }.get(frame.type)
        if frame_type is None:
            raise NotImplementedError("Unsupported frame type", frame.type)
        return frame_type.from_raw(frame)
