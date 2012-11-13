import logging
from socket import socket, AF_INET, SOCK_DGRAM

from myvpn.tun import Tun
from myvpn.utils import populate_common_argument_parser, proxy
from myvpn.consts import MAGIC_WORD

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    populate_common_argument_parser(parser)
    parser.add_argument('--ip', default='192.168.5.1',
                        help="[default: %(default)s]")
    parser.add_argument('--peer-ip', default='192.168.5.2',
                        help="[default: %(default)s]")

def main(args):
    tun = Tun(device=args.device, ip=args.ip, peer_ip=args.peer_ip)
    tun.open()

    sock = socket(AF_INET, SOCK_DGRAM)

    try:
        sock.bind(('0.0.0.0', args.port))

        while 1:
            word, peer = sock.recvfrom(1500)
            if word == MAGIC_WORD:
                logger.debug("handshake")
                break
            logger.warning("bad magic word for %s:%i" % peer)

        sock.sendto(MAGIC_WORD, peer)

        proxy(tun.fd, sock, peer)

    except KeyboardInterrupt:
        logger.warning("user stop")
