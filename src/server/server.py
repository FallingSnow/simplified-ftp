from socket import socket, AF_INET, SOCK_STREAM, timeout
from threading import Thread
from queue import Queue


class Server:
    def __init__(self, _logger, config):
        self._logger = _logger

        # Setup config with defaults
        self.config = {
            'bytes_per_message': 1024,
            'accept_timeout': 0.2,
            'recv_timeout': 0.2
        }
        self.config.update(config)

        # This msgQueue can be used to communicate messages to the server thread
        # See the commented out section in run for more info
        self.msgQueue = Queue()
        self.socket = socket(AF_INET, SOCK_STREAM)

        # Set timeout for self.socket.accept
        self.socket.settimeout(self.config['accept_timeout'])
        self.done = False

    def listen(self, port):
        self.socket.bind(('', port))
        self.socket.listen(1)
        thread = Thread(target=self.run, args=())
        thread.start()
        self._logger.debug("Server listening on {}".format(port))
        return thread

    def close(self):
        self.done = True

    def run(self):
        while not self.done:

            # # Check queue events (messages from parent)
            # while not self.receiveQueue.empty():
            #     if self.receiveQueue.get() == "end":
            #         self.done = True

            # The accept will timeout if it does not receive a connection in
            # time
            try:
                client, addr = self.socket.accept()
                client.settimeout(self.config['recv_timeout'])
            except timeout:
                continue

            data = bytes()

            while len(data) < self.config['bytes_per_message']:

                try:
                    buffer = client.recv(self.config['bytes_per_message'])
                except timeout:
                    break

                if not buffer:
                    break

                data += buffer

            client.close()
