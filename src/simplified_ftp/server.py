from threading import Thread
from queue import Queue
from message import Message, MessageType
import socket
import select


class Connection:
    def __init__(self, _logger, socket, address="unknown", fileroot='/tmp'):
        self._logger = _logger
        self.socket = socket
        self.address = address
        # Create a buffer byte array for our client
        self.buffer = b""
        self.responses = {}
        self.lostMessages = set()
        self.lastMessageId = 0
        self.file = False
        self.fileroot = fileroot

    # Close our socket and cleanup
    def close(self):
        self.socket.close()
        # Close any open files
        if self.fileIsOpen():
            self.file.close()

    def processMessage(self, message):

        # Keep track of any non sequental messages
        for lostId in range(self.lastMessageId + 1, message.id):
            self.lostMessages.add(lostId)
        self.lastMessageId = message.id

        # If our message was in listMessages, lets remove it
        # This can happen if messages arrive out of sequential id order
        self.lostMessages.discard(message.id)

        # ### Process the message depending on what type of message it is
        if message.type == MessageType.FileStart:

            # If FileStart, open a new file for writing to
            self.file = open(
                "{0}/{1}".format(self.fileroot, message.filename), "wb")
            self._logger.debug(
                "Opened: {}".format(message.filename))

        if message.type in MessageType.File:

            # Check if a file was never opened for this connection
            if not self.fileIsOpen():
                raise RuntimeError("No file opened")

            # All File message types have a content, lets write that to the
            # file.
            self.file.write(message.content)
            self._logger.debug("Wrote {}.".format(
                message.content))

        # We can go ahead and close the file if we receive a FileEnd message
        if message.type == MessageType.FileEnd:
            self.file.close()

    def processBuffer(self, buffer):
        # Add this events buffer to our overall buffer
        self.buffer += buffer

        # Our packets are terminated with a null terminator (\0).
        # If we find one we know we have received a whole packet.
        packetMarkerPosition = self.buffer.find(b'\0')
        while packetMarkerPosition != -1:
            try:

                # Extract our packet from the buffer
                messageBuffer = self.buffer[:packetMarkerPosition]

                # Attempt to convert our packet into a message
                message = Message.fromBytes(messageBuffer)
                self._logger.debug("Got a {} message!".format(message.type.name))

                self.processMessage(message)

            # If we have any issues running the above code, such as failing to
            # parse the incoming bytes into a valid message, we should log that
            # error.
            except RuntimeError as err:
                self._logger.error(err)
            finally:
                # Trim the buffer of packet we just processed
                self.buffer = self.buffer[packetMarkerPosition + 1:]

                # Check if there is another whole packet in the buffer
                packetMarkerPosition = self.buffer.find(
                    b'\0')

    def recv(self, bufferSize):
        buffer = self.socket.recv(bufferSize)
        # If we get an empty message, when know the communication channel
        # has been closed
        if len(buffer) == 0:
            self.shutdown()
            return 0

        self._logger.debug("Got bytes: {0}".format(buffer))

        self.processBuffer(buffer)

        return None

    def fileIsOpen(self):
        return self.file and not self.file.closed

    def shutdown(self):
        self.socket.shutdown(socket.SHUT_RDWR)


class Server:
    def __init__(self, _logger, config):
        self._logger = _logger

        # Setup config with defaults
        self.config = {
            'file_root': '/tmp',
            'event_timeout': 0.2,
            'internal_recv_size': 8192
        }
        self.config.update(config)

        # This msgQueue can be used to communicate messages to the server thread
        # See the commented out section in run for more info
        self.msgQueue = Queue()

        # Open a new socket to listen on
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Set the socket to reuse old port if server is restarted
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # This is set to true when we want to end the server loop
        self.done = False

    def listen(self, port, addr='0.0.0.0'):

        # Sets the interface and port number for the socket to listen for connections
        # on.
        self.socket.bind((addr, port))
        self.socket.listen(1)

        # In order to prevent locking up the main thread, we start a new child thread.
        # This child thread will continously run the server's loop function and
        # check self.done periodically if to see if it should end
        thread = Thread(target=self.loop, args=())
        thread.start()

        self._logger.debug("Server listening on {}".format(port))

        # We will return the thread handle so that it can be acted on in the future
        return thread

    def close(self):
        self.done = True

    def loop(self):

        connections = {}

        # See http://scotdoyle.com/python-epoll-howto.html for a detailed
        # explination on the epoll interface
        epoll = select.epoll()

        # We register our socket server in EPOLLIN mode to watch for incomming
        # connections.
        epoll.register(self.socket.fileno(), select.EPOLLIN)
        try:

            # Check if we should end our loop
            while not self.done:

                # This will return any new events
                events = epoll.poll(self.config['event_timeout'])

                # Process any new events
                for fileno, event in events:

                    # This handles a new connection
                    if fileno == self.socket.fileno():
                        client, address = self.socket.accept()
                        client.setblocking(0)
                        self._logger.info(
                            "New connection from {0}".format(address))

                        # Store our client in a connections dictionary
                        connections[client.fileno()] = Connection(self._logger, client, address, self.config['file_root'])

                        # Register incomming client connection with our epoll interface
                        epoll.register(client.fileno(), select.EPOLLIN)

                    # This event is called when there is data to be read in
                    elif event & select.EPOLLIN:

                        # Try to receive data from our client
                        mode = connections[fileno].recv(self.config['internal_recv_size'])

                        if mode is not None:
                            epoll.modify(fileno, mode)


                        # Check if transmission is complete. In our case we are
                        # using an NULL termination (\0)
                        # Now that we know the transmission is complete, we should
                        # send a response (switch to send mode)
                        # if not buffers[fileno].endswith(b'\\\\0') and buffers[fileno].endswith(b'\\0'):
                        #     responses[fileno]  = b'HTTP/1.0 200 OK\r\nDate: Mon, 1 Jan 1996 01:01:01 GMT\r\n'
                        #     responses[fileno] += b'Content-Type: text/plain\r\nContent-Length: 13\r\n\r\n'
                        #     responses[fileno] += b'Hello, world!'
                        #     epoll.modify(fileno, select.EPOLLOUT)
                        # Server.parse_message(buffers[fileno])

                    # This event is called when there is data to be written out
                    elif event & select.EPOLLOUT:
                        pass
                        # # Send out our response
                        # numBytesWritten = connections[fileno].send(
                        #     responses[fileno])
                        # self._logger.debug("Sent response: {0}".format(
                        #     responses[fileno][:numBytesWritten]))
                        #
                        # # Truncate our response buffer (remove the part that is
                        # # already sent)
                        # responses[fileno] = responses[fileno][numBytesWritten:]
                        # self._logger.debug(responses[fileno])
                        #
                        # if len(responses[fileno]) == 0:
                        #     epoll.modify(fileno, select.EPOLLIN)

                    # Endpoint has closed the connection (No need to send shutdown)
                    elif event & select.EPOLLHUP:
                        self._logger.debug("Connection to [{}] closed!".format(connections[fileno].address))
                        self._logger.debug("Lost packets: {}".format(connections[fileno].lostMessages))
                        epoll.unregister(fileno)
                        connections[fileno].close()
                        del connections[fileno]
        finally:

            # Close all open connections
            self._logger.debug("Closing all connections...")
            for fileno in connections:
                epoll.unregister(fileno)
                connections[fileno].close()

            # Unregister our server socket with our epoll
            epoll.unregister(self.socket.fileno())

            # Close our epoll
            epoll.close()

            # Close our socket server
            self.socket.close()

            self._logger.info("Server shutdown")
