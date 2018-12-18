from threading import Thread
from message import Message, MessageType
import queue
import socket
import select
import os


class Client:
    def __init__(self, logger, config):
        self._logger = logger
        self.messageCounter = 0

        # Setup config with defaults
        self.config = {
            'event_timeout': 0.2,
            'command_queue_timeout': 0.2,
            'max_concurrent_packets': 5,
            'file_segment_size': 1024  # Bytes
        }
        self.config.update(config)

        self.commandQueue = queue.Queue()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.done = False

    def getMessageId(self):
        self.messageCounter += 1
        return self.messageCounter

    def connect(self, port, addr='127.0.0.1'):
        self.socket.connect((addr, port))
        thread = Thread(target=self.loop, args=())
        thread.start()
        self._logger.debug(
            "Client connected to {addr}:{port}".format(addr=addr, port=port))
        return thread

    def close(self):
        self.done = True

    def sendFile(self, filepath):
        offset = 0
        segmentSize = self.config['file_segment_size']
        endSent = False
        filename = os.path.basename(filepath)

        # Open a file to read from
        with open(filepath, 'rb') as file:
            file.seek(offset)
            fileBuffer = file.read(segmentSize)
            offset += len(fileBuffer)
            yield Message(id=self.getMessageId(), type=MessageType.FileStart, filename=filename, content=fileBuffer)

            file.seek(offset)
            fileBuffer = file.read(segmentSize)
            offset += len(fileBuffer)
            while len(fileBuffer) != 0:
                if len(fileBuffer) < segmentSize:
                    yield Message(id=self.getMessageId(), type=MessageType.FileEnd, content=fileBuffer)
                    endSent = True
                    break
                else:
                    yield Message(id=self.getMessageId(), type=MessageType.FilePart, content=fileBuffer)
                    file.seek(offset)
                    fileBuffer = file.read(segmentSize)
                    offset += len(fileBuffer)
            file.close()
        if not endSent:
            yield Message(id=self.getMessageId(), type=MessageType.FileEnd, content=b"")

    def loop(self):
        transmittingMessages = {}

        # See http://scotdoyle.com/python-epoll-howto.html for a detailed
        # explination on the epoll interface
        epoll = select.epoll()
        epoll.register(self.socket.fileno(), select.EPOLLOUT)
        try:
            while not self.done:
                events = epoll.poll(self.config['event_timeout'])

                # Process events from epoll
                for fileno, event in events:

                    # If socket is in EPOLLOUT state
                    if event & select.EPOLLOUT:
                        try:

                            # Check for commands to process
                            command = self.commandQueue.get(
                                True, self.config['command_queue_timeout'])

                            # Commands are generators so we can iterate over them
                            # to get all of their messages.
                            for message in command:
                                transmittingMessages[message.id] = message
                                self._logger.debug(
                                    "Sending: {}".format(message.toBytes()))
                                self.socket.send(message.toBytes())

                        except queue.Empty:
                            continue

                    if event & select.EPOLLIN:
                        self._logger.debug(
                            "Got data {}".format(self.socket.recv(10)))

                    elif event & select.EPOLLHUP:
                        self._logger.info("Server closed connection.")
        finally:

            epoll.unregister(self.socket.fileno())
            epoll.close()
            self.socket.close()
