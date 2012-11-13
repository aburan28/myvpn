from socket import socket
import logging

from myvpn.tun import Tun
from myvpn.utils import populate_common_argument_parser, proxy

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    populate_common_argument_parser(parser)
    parser.add_argument('--server', required=True)

def main(args):
    tun = Tun(args.ip, device=args.device)
    tun.open()

    sock = socket()
    sock.connect((args.server, args.port))
    logger.info("Connected to server")

    proxy(tun, sock)
