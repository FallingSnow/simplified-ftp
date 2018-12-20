from enum import IntFlag, unique

# ################# PROTOCOL DEFINITION ###################
#
# Checksums are CRC-32C. All messages end it a \0 termination character.
#
# Messages are UTF-8 encoded with a binary CONTENT field.
#
# FileStart: [PROTOCOL]/[VERSION] [TYPE] [FILENAME] [CONTENT]
#   Example: SimFTP/0.1 0 file.txt laseuybjaw3blk23r89nzjx
# FilePart: [PROTOCOL]/[VERSION] [TYPE] [CONTENT]
#   Example: SimFTP/0.1 1 laseuybjaw3blk23r89nzjx
# FileEnd: [PROTOCOL]/[VERSION] [TYPE] [CONTENT]
#   Example: SimFTP/0.1 2 laseuybjaw3blk23r89nzjx
# TODO: Error: [PROTOCOL]/[VERSION] [TYPE] [CONTENT]
#   Example: SimFTP/0.1 128 laseuybjaw3blk23r89nzjx


# Define message types that can be transmitted or received
@unique
class MessageType(IntFlag):
    FileStart = int('0000_0001', 2)
    FilePart = int('0000_0010', 2)
    FileEnd = int('0000_0100', 2)
    File = FileStart | FilePart | FileEnd
    Error = int('1000_0000', 2)


# Message formats are the layout for each packet of a certain message type
MESSAGE_FORMATS = {
    MessageType.FileStart: "{self.protocol}/{self.version} {self.type} {self.filename} ",
    MessageType.FilePart: "{self.protocol}/{self.version} {self.type} ",
    MessageType.FileEnd: "{self.protocol}/{self.version} {self.type} ",
}


class Message:
    PROTOCOL_FORMAT = "{protocol}/{version} {type}"
    VERSION = "0.1"
    PROTOCOL = "SimFTP"
    MINIMUM_SIZE = len(PROTOCOL_FORMAT.format(
        protocol=PROTOCOL,
        version=VERSION,
        id=0,
        type=0,
        content=b""
    )) + 8 + 1  # +8 for checksum, +1 for \0 (one control character)

    def __init__(self, **params):

        # Define protocol and version of the message.
        # These are predefined based on the version of simplified-ftp
        self.protocol = Message.PROTOCOL  # params.protocol
        self.version = Message.VERSION  # params.version
        self.type = params['type']

        # Define addition properties on message based on message type
        if self.type == MessageType.FileStart:
            self.filename = params['filename']
        if self.type in MessageType.File:
            self.content = params['content']

    def fromBytes(bytes):

        assert len(bytes) >= Message.MINIMUM_SIZE

        params = {}

        # Protocol is the first 6 bytes (SimFTP), first 6 characters
        protocol = bytes[:6]

        # Version is first 3 bytes (0.1)
        version = bytes[7:10]

        # Same as id, type is variable length
        typeEnd = bytes.find(b' ', 11)
        params['type'] = MessageType(
            int(bytes[11:typeEnd].decode('utf-8')))

        # ### Do some message data validation

        # Ensure the supplied type is a known message type.
        if params['type'].name is None:
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
        if params['type'] == MessageType.FileStart:
            filenameEnd = bytes.find(b' ', typeEnd + 1)
            params['filename'] = bytes[typeEnd + 1:filenameEnd].decode('utf-8')
            params['content'] = bytes[filenameEnd + 1:]

        # FilePart & FileEnd will have contents after their message type field
        elif params['type'] == MessageType.FilePart or params['type'] == MessageType.FileEnd:
            params['content'] = bytes[typeEnd + 1:]

        # Construct a new message and return it
        return Message(**params)

    def toBytes(self):

        # Use MESSAGE_FORMATS[type] to define the basic structure of the message
        bytes = MESSAGE_FORMATS[self.type].format(
            self=self
        ).encode('utf-8')

        # Add message content
        if self.type in MessageType.File:
            bytes += self.content

        bytes += b"\0"

        # Ensure our message fufills the basic requirements
        assert len(bytes) >= Message.MINIMUM_SIZE

        # Return our generated message bytes
        return bytes
