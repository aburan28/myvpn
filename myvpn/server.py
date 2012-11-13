import logging
from socket import socket, SOL_SOCKET, SO_REUSEADDR

from myvpn.tun import Tun
from myvpn.utils import populate_common_argument_parser, proxy

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    populate_common_argument_parser(parser)

def main(args):
    tun = Tun(args.ip, device=args.device)
    tun.open()

    sock = socket()
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', args.port))
    sock.listen(1)
    client, client_addr = sock.accept()
    logger.info("Client %s connected", client_addr)

    proxy(tun, client)
