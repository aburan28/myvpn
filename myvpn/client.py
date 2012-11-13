import sys
from socket import socket, AF_INET, SOCK_DGRAM
import logging

from myvpn.tun import Tun
from myvpn.utils import populate_common_argument_parser, proxy
from myvpn.consts import MAGIC_WORD

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    populate_common_argument_parser(parser)
    parser.add_argument('--server', required=True)
    parser.add_argument('--ip', default='192.168.5.2',
                        help="[default: %(default)s]")
    parser.add_argument('--peer-ip', default='192.168.5.1',
                        help="[default: %(default)s]")

def main(args):
    tun = Tun(device=args.device, ip=args.ip, peer_ip=args.peer_ip)
    tun.open()

    sock = socket(AF_INET, SOCK_DGRAM)

    try:
        sock.sendto(MAGIC_WORD, (args.server, args.port))
        word, peer = sock.recvfrom(1500)
        if word != MAGIC_WORD:
            logger.warning("Bad magic word for %s:%i" % peer)
            sys.exit(2)
        logger.info("Connection with %s:%i established" % peer)

        proxy(tun.fd, sock, peer)

    except KeyboardInterrupt:
        logger.warning("Stopped by user")
