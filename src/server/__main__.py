import argparse
import sys
import signal
import logging
from time import sleep
from queue import Queue

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
        description="Just a Fibonnaci demonstration")
    parser.add_argument(
        '--version',
        action='version',
        version='simplified-ftp-server {ver}'.format(ver=__version__))
    parser.add_argument(
        '-p',
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
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")

def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)
    _logger.debug("Starting server...")

    server = Server(_logger, {})
    server.listen(args.port)

    def close_server(sig, frame):
        print("Closing Server Cleanly")
        server.close()

    # This listens for sigint (ctrl-c) and calls an inline function (lambda) to
    # stop the server
    signal.signal(signal.SIGINT, close_server)

def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
