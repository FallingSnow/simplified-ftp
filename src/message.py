from enum import IntFlag, unique
from crc32c import crc32

# ################# PROTOCOL DEFINITION ###################
#
# Checksums are CRC-32C. All messages end it a \0 termination character.
#
# FileStart: [PROTOCOL]/[VERSION] [ID] [TYPE] [FILENAME] [CONTENT] [CHECKSUM]\0
#   Example: SimFTP/0.1 38274 0 file.txt laseuybjaw3blk23r89nzjx 7DD9F3E8\0
# FilePart: [PROTOCOL]/[VERSION] [ID] [TYPE] [CONTENT] [CHECKSUM]\0
#   Example: SimFTP/0.1 38275 1 laseuybjaw3blk23r89nzjx DACEA4B9\0
# FileEnd: [PROTOCOL]/[VERSION] [ID] [TYPE] [CONTENT] [CHECKSUM]\0
#   Example: SimFTP/0.1 38276 2 laseuybjaw3blk23r89nzjx 4AD04FFE\0
# Acknowledge: [PROTOCOL]/[VERSION] [ID] [TYPE] [PACKETS(,)] [CHECKSUM]\0
#   Example: SimFTP/0.1 38277 16 38274,38275,38276 C49537D6\0
# TODO: Error: [PROTOCOL]/[VERSION] [ID] [TYPE] [CONTENT] [CHECKSUM]\0
#   Example: SimFTP/0.1 38278 128 laseuybjaw3blk23r89nzjx 892e3af3\0


# Define message types that can be transmitted or received
@unique
class MessageType(IntFlag):
    FileStart = int('0000_0001', 2)
    FilePart = int('0000_0010', 2)
    FileEnd = int('0000_0100', 2)
    File = FileStart | FilePart | FileEnd
    Acknowledge = int('0000_1000', 2)
    Error = int('1000_0000', 2)


MESSAGE_FORMATS = {
    MessageType.FileStart: "{protocol}/{version} {id} {type} {filename} {content} ",
    MessageType.FilePart: "{protocol}/{version} {id} {type} {content} ",
    MessageType.FileEnd: "{protocol}/{version} {id} {type} {content} ",
}


class Message:
    PROTOCOL_FORMAT = "{protocol}/{version} {id} {type}"
    VERSION = "0.1"
    PROTOCOL = "SimFTP"
    MINIMUM_SIZE = len(PROTOCOL_FORMAT.format(
        protocol=PROTOCOL,
        version=VERSION,
        id=0,
        type=0,
        content=""
    )) + 8 + 1  # +8 for checksum, +1 for \0 (one control character)
    MAXIMUM_SIZE = MINIMUM_SIZE + 1024

    def __init__(self, id, type, filename="", content=""):
        # self.logger = logger

        self.protocol = Message.PROTOCOL  # params.protocol
        self.version = Message.VERSION  # params.version
        self.id = id
        self.type = type

        if self.type == MessageType.FileStart:
            self.filename = filename
        if self.type in MessageType.File:
            self.content = content

        # if logger:
        #     logger.debug("Protocol: {0}".format(self.protocol))
        #     logger.debug("Version: {0}".format(self.version))
        #     logger.debug("Id: {0}".format(self.id))
        #     logger.debug("Type: {0}".format(self.type.name))

    def fromBytes(bytes):

        assert len(bytes) <= Message.MAXIMUM_SIZE and len(
            bytes) >= Message.MINIMUM_SIZE

        # Validate message checksum
        checksum = bytes[-8:].decode('utf-8')
        calculatedChecksum = hex(crc32(bytes[:-8]))[2:]
        if checksum != calculatedChecksum:
            raise RuntimeError("Invalid checksum: {} != {}".format(
                checksum, calculatedChecksum))

        protocol = bytes[:6]
        version = bytes[7:10]
        idEnd = bytes.find(b' ', 11)
        id = int(bytes[10:idEnd].decode('utf-8'))
        typeEnd = bytes.find(b' ', idEnd + 1)
        type = MessageType(int(bytes[idEnd + 1:typeEnd].decode('utf-8')))

        if type.name is None:
            raise RuntimeError("Invalid message type: {}".format(type))

        if protocol.decode('utf-8') != Message.PROTOCOL:
            raise RuntimeError(
                "Unknown message protocol: {}".format(protocol.decode()))
        if version.decode('utf-8') != Message.VERSION:
            raise RuntimeError(
                "Unknown protocol version: {}".format(version.decode()))

        if type == MessageType.FileStart:
            filenameEnd = bytes.find(b' ', typeEnd + 1)
            filename = bytes[typeEnd + 1:filenameEnd].decode('utf-8')
            content = bytes[filenameEnd + 1:-9].decode('utf-8')
        elif type == Message.FilePart or type == Message.FileEnd:
            content = bytes[typeEnd + 1:-9].decode('utf-8')

        return Message(id=id, type=type, filename=filename, content=content)

    def toBytes(self):

        bytes = MESSAGE_FORMATS[self.type].format(
            protocol=self.protocol,
            version=self.version,
            id=self.id,
            type=self.type.value,
            filename=self.filename,
            content=self.content
        ).encode('utf-8')

        bytes += "{}\0".format(hex(crc32(bytes))[2:]).encode('utf-8')

        assert len(bytes) <= Message.MAXIMUM_SIZE and len(
            bytes) >= Message.MINIMUM_SIZE

        return bytes
