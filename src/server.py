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
        }
        self.config.update(config)

        # This msgQueue can be used to communicate messages to the server thread
        # See the commented out section in run for more info
        self.msgQueue = Queue()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.done = False

    def listen(self, port, addr='0.0.0.0'):
        self.socket.bind((addr, port))
        self.socket.listen(1)
        thread = Thread(target=self.loop, args=())
        thread.start()
        self._logger.debug("Server listening on {}".format(port))
        return thread

    def close(self):
        self.done = True

    def loop(self):

        connections = {}
        buffers = {}
        responses = {}
        files = {}

        def closeConnection(fileno):
            if files[fileno]:
                files[fileno].close()
            epoll.unregister(fileno)
            connections[fileno].close()
            del connections[fileno]

        # See http://scotdoyle.com/python-epoll-howto.html for a detailed
        # explination on the epoll interface
        epoll = select.epoll()
        epoll.register(self.socket.fileno(), select.EPOLLIN)
        try:
            while not self.done:
                # # Check queue events (messages from parent)
                # while not self.msgQueue.empty():
                #     if self.msgQueue.get() == "end":
                #         self.done = True

                # This will return any new events
                events = epoll.poll(self.config['event_timeout'])
                for fileno, event in events:
                    if fileno == self.socket.fileno():
                        client, address = self.socket.accept()
                        client.setblocking(0)
                        self._logger.info(
                            "New connection from {0}".format(address))

                        epoll.register(client.fileno(), select.EPOLLIN)

                        # Store our client in a connections dictionary
                        connections[client.fileno()] = client

                        # Create a buffer byte array for our client
                        buffers[client.fileno()] = b''
                    elif event & select.EPOLLIN:

                        # Try to receive data from our client
                        buffer = connections[fileno].recv(Message.MINIMUM_SIZE)

                        # If we get an empty message, when know the communication channel
                        # has been closed
                        if len(buffer) == 0:
                            epoll.modify(fileno, 0)
                            connections[fileno].shutdown(socket.SHUT_RDWR)
                            continue

                        self._logger.debug("Got bytes: {0}".format(buffer))

                        # Add this events buffer to our overall buffer
                        buffers[fileno] += buffer

                        packetMarkerPosition = buffers[fileno].find(b'\0')
                        while packetMarkerPosition != -1:
                            try:
                                messageBuffer = buffers[fileno][:packetMarkerPosition]
                                message = Message.fromBytes(messageBuffer)
                                self._logger.debug("Got valid message!")
                                if message.type == MessageType.FileStart:
                                    files[fileno] = open(
                                        "/tmp/{0}".format(message.filename), "w")
                                    self._logger.debug(
                                        "Opened: {}".format(message.filename))

                                if message.type in MessageType.File:
                                    if fileno not in files:
                                        raise RuntimeError("No file selected")
                                    files[fileno].write(message.content)
                                    self._logger.debug("Wrote \"{}\" to {}".format(
                                        message.content, message.filename))

                                if message.type == MessageType.FileEnd:
                                    files[fileno].close()
                            except RuntimeError as err:
                                self._logger.error(err)
                            finally:
                                buffers[fileno] = buffers[fileno][packetMarkerPosition + 1:]
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
                        print(responses[fileno])

                        if len(responses[fileno]) == 0:
                            epoll.modify(fileno, select.EPOLLIN)

                    # Endpoint has closed the connection (No need to send shutdown)
                    elif event & select.EPOLLHUP:
                        self._logger.debug("Connection closed!")
                        closeConnection(fileno)
        finally:
            self._logger.debug("Closing connections...")
            for fileno, connection in connections.items():
                closeConnection(fileno)

            del connections

            epoll.unregister(self.socket.fileno())
            epoll.close()
            self.socket.close()
