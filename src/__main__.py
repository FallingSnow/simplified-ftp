import argparse
import sys
import signal
import logging

from client import Client
from server import Server

__author__ = "Ayrton Sparling"
__copyright__ = "Ayrton Sparling"
__license__ = "mit"
__version__ = "0.1"

_logger = logging.getLogger(__name__)
_done = 0


def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="The SimFTP file transfer system")
    parser.add_argument(
        '--version',
        action='version',
        version='simplified-ftp-client {ver}'.format(ver=__version__))
    parser.add_argument(
        '--host',
        dest="host",
        default="127.0.0.1")
    parser.add_argument(
        '--port',
        dest="port",
        type=int,
        default=7240)
    parser.add_argument(
        '-v',
        '--verbose',
        dest="loglevel",
        help="set loglevel to INFO",
        action='store_const',
        const=logging.INFO)
    parser.add_argument(
        '-vv',
        '--very-verbose',
        dest="loglevel",
        help="set loglevel to DEBUG",
        action='store_const',
        const=logging.DEBUG)
    parser.add_argument(
        "system",
        help="start either the client or server",
        choices=['server', 'client']
    )
    parser.add_argument(
        "-s",
        "--send",
        metavar="PATH",
        help="path to file that client should send to server",
    )
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")


def start_client(args):
    client = Client(_logger, {})
    client.connect(args.port, args.host)

    return client


def start_server(args):
    server = Server(_logger, {})
    server.listen(args.port)

    return server


def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    _logger.debug("Starting client...")

    if args.system == 'server':
        connection = start_server(args)
    elif args.system == 'client':
        connection = start_client(args)
        if args.send:
            connection.commandQueue.put(connection.sendFile(args.send))

    # This function is called when a sigint is caught and closes the server
    def close(sig, frame):
        _logger.info("Closing service...")
        connection.close()

    # This listens for sigint (ctrl-c) and calls an inline function (lambda) to
    # stop the server (Only works on non-windows)
    signal.signal(signal.SIGINT, close)


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
