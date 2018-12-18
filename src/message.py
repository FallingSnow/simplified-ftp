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


# Message formats are the layout for each packet of a certain message type
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

        # Define protocol and version of the message.
        # These are predefined based on the version of simplified-ftp
        self.protocol = Message.PROTOCOL  # params.protocol
        self.version = Message.VERSION  # params.version
        self.id = id
        self.type = type

        # Define addition properties on message based on message type
        if self.type == MessageType.FileStart:
            self.filename = filename
        if self.type in MessageType.File:
            self.content = content

    def fromBytes(bytes):

        assert len(bytes) <= Message.MAXIMUM_SIZE and len(
            bytes) >= Message.MINIMUM_SIZE

        # ### Validate message checksum
        # Get checksum from bytes
        checksum = bytes[-8:].decode('utf-8')

        # Calculate our own checksum for the message and convert it to hex
        calculatedChecksum = hex(crc32(bytes[:-8]))[2:]

        # Check if our calculated checksum matches the checksum provided in the
        # message.
        if checksum != calculatedChecksum:
            raise RuntimeError("Invalid checksum: {} != {}".format(
                checksum, calculatedChecksum))

        # Protocol is the first 6 bytes (SimFTP), first 6 characters
        protocol = bytes[:6]

        # Version is first 3 bytes (0.1)
        version = bytes[7:10]

        # ID has a variable length and is delimited by a single space.
        # Therefore we look for the next space after the space after version
        idEnd = bytes.find(b' ', 11)
        id = int(bytes[10:idEnd].decode('utf-8'))

        # Same as id, type is variable length
        typeEnd = bytes.find(b' ', idEnd + 1)
        type = MessageType(int(bytes[idEnd + 1:typeEnd].decode('utf-8')))



        # ### Do some message data validation

        # Ensure the supplied type is a known message type.
        if type.name is None:
            raise RuntimeError("Invalid message type: {}".format(type))

        # Ensure the supplied protocol is the expect protocol
        if protocol.decode('utf-8') != Message.PROTOCOL:
            raise RuntimeError(
                "Unknown message protocol: {}".format(protocol.decode()))

        # Ensure the supplied protocol version is the expect protocol version
        if version.decode('utf-8') != Message.VERSION:
            raise RuntimeError(
                "Unknown protocol version: {}".format(version.decode()))

        # Add additional properties to the message depending on message type
        if type == MessageType.FileStart:
            filenameEnd = bytes.find(b' ', typeEnd + 1)
            filename = bytes[typeEnd + 1:filenameEnd].decode('utf-8')
            content = bytes[filenameEnd + 1:-9].decode('utf-8')

        # FilePart & FileEnd will have contents after their message type field
        elif type == Message.FilePart or type == Message.FileEnd:
            content = bytes[typeEnd + 1:-9].decode('utf-8')

        # Construct a new message and return it
        return Message(id=id, type=type, filename=filename, content=content)

    def toBytes(self):

        # Use MESSAGE_FORMATS[type] to define the basic structure of the message
        bytes = MESSAGE_FORMATS[self.type].format(
            protocol=self.protocol,
            version=self.version,
            id=self.id,
            type=self.type.value,
            filename=self.filename,
            content=self.content
        ).encode('utf-8')

        # Calculate and append the crc32 checksum in hex
        bytes += "{}\0".format(hex(crc32(bytes))[2:]).encode('utf-8')

        # Ensure our message fufills the basic requirements
        assert len(bytes) <= Message.MAXIMUM_SIZE and len(
            bytes) >= Message.MINIMUM_SIZE

        # Return our generated message bytes
        return bytes
