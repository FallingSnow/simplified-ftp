from threading import Thread
from queue import Queue
from message import Message, MessageType
import socket
import select


class Server:
    def __init__(self, _logger, config):
        self._logger = _logger

        # Setup config with defaults
        self.config = {
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
        buffers = {}
        responses = {}
        files = {}

        # This close helper function that just closes a connection and cleans up
        # after it.
        def closeConnection(fileno):
            if fileno in files:
                files[fileno].close()
                del files[fileno]
            epoll.unregister(fileno)
            connections[fileno].close()

        # See http://scotdoyle.com/python-epoll-howto.html for a detailed
        # explination on the epoll interface
        epoll = select.epoll()

        # We register our socket server in EPOLLIN mode to watch for incomming
        # connections.
        epoll.register(self.socket.fileno(), select.EPOLLIN)
        try:

            # Check if we should end our loop
            while not self.done:
                # # Check queue events (messages from parent)
                # while not self.msgQueue.empty():
                #     if self.msgQueue.get() == "end":
                #         self.done = True

                # This will return any new events
                events = epoll.poll(self.config['event_timeout'])

                # Process any new events
                for fileno, event in events:
                    if fileno == self.socket.fileno():
                        client, address = self.socket.accept()
                        client.setblocking(0)
                        self._logger.info(
                            "New connection from {0}".format(address))

                        # Register incomming client connection with our epoll interface
                        epoll.register(client.fileno(), select.EPOLLIN)

                        # Store our client in a connections dictionary
                        connections[client.fileno()] = client

                        # Create a buffer byte array for our client
                        buffers[client.fileno()] = b''
                    elif event & select.EPOLLIN:

                        # Try to receive data from our client
                        buffer = connections[fileno].recv(self.config['internal_recv_size'])

                        # If we get an empty message, when know the communication channel
                        # has been closed
                        if len(buffer) == 0:
                            epoll.modify(fileno, 0)
                            connections[fileno].shutdown(socket.SHUT_RDWR)
                            continue

                        self._logger.debug("Got bytes: {0}".format(buffer))

                        # Add this events buffer to our overall buffer
                        buffers[fileno] += buffer

                        # Our packets are terminated with a null terminator (\0).
                        # If we find one we know we have received a whole packet.
                        packetMarkerPosition = buffers[fileno].find(b'\0')
                        while packetMarkerPosition != -1:
                            try:

                                # Extract our packet from the buffer
                                messageBuffer = buffers[fileno][:packetMarkerPosition]

                                # Attempt to convert our packet into a message
                                message = Message.fromBytes(messageBuffer)
                                self._logger.debug("Got a {} message!".format(message.type.name))

                                # ### Process the message depending on what type of message it is
                                if message.type == MessageType.FileStart:

                                    # If FileStart, open a new file for writing to
                                    files[fileno] = open(
                                        "/tmp/{0}".format(message.filename), "wb")
                                    self._logger.debug(
                                        "Opened: {}".format(message.filename))

                                if message.type in MessageType.File:

                                    # Check if a file was never opened for this connection
                                    if fileno not in files:
                                        raise RuntimeError("No file selected")

                                    # All File message types have a content, lets write that to the
                                    # file.
                                    files[fileno].write(message.content)
                                    self._logger.debug("Wrote {}.".format(
                                        message.content))

                                # We can go ahead and close the file if we receive a FileEnd message
                                if message.type == MessageType.FileEnd:
                                    files[fileno].close()

                            # If we have any issues running the above code, such as failing to
                            # parse the incoming bytes into a valid message, we should log that
                            # error.
                            except RuntimeError as err:
                                self._logger.error(err)
                            finally:
                                # Trim the buffer of packet we just processed
                                buffers[fileno] = buffers[fileno][packetMarkerPosition + 1:]

                                # Check if there is another whole packet in the buffer
                                packetMarkerPosition = buffers[fileno].find(
                                    b'\0')

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
                    elif event & select.EPOLLOUT:

                        # Send out our response
                        numBytesWritten = connections[fileno].send(
                            responses[fileno])
                        self._logger.debug("Sent response: {0}".format(
                            responses[fileno][:numBytesWritten]))

                        # Truncate our response buffer (remove the part that is
                        # already sent)
                        responses[fileno] = responses[fileno][numBytesWritten:]
                        self._logger.debug(responses[fileno])

                        if len(responses[fileno]) == 0:
                            epoll.modify(fileno, select.EPOLLIN)

                    # Endpoint has closed the connection (No need to send shutdown)
                    elif event & select.EPOLLHUP:
                        self._logger.debug("Connection closed!")
                        closeConnection(fileno)
                        del connections[fileno]
        finally:

            # Close all open connections
            self._logger.debug("Closing connections...")
            for fileno in connections:
                closeConnection(fileno)

            # Unregister our server socket with our epoll
            epoll.unregister(self.socket.fileno())

            # Close our epoll
            epoll.close()

            # Close our socket server
            self.socket.close()
