import logging
from socket import socket, AF_INET, SOCK_DGRAM
from subprocess import check_call, call

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

    netseg = '.'.join(args.ip.split('.')[:3] + ['0/24'])
    call(['iptables', '-t', 'nat', '-D', 'POSTROUTING', '-s', netseg, '-j', 'MASQUERADE'])
    check_call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-s', netseg, '-j', 'MASQUERADE'])

    sock = socket(AF_INET, SOCK_DGRAM)

    try:
        sock.bind(('0.0.0.0', args.port))

        while 1:
            word, peer = sock.recvfrom(1500)
            if word == MAGIC_WORD:
                break
            logger.warning("bad magic word for %s:%i" % peer)

        while 1:
            logger.info("handshake from %s:%i" % peer)
            sock.sendto(MAGIC_WORD, peer)

            retval = proxy(tun.fd, sock, peer, break_on_packet=MAGIC_WORD)
            if type(retval) is tuple and retval[0] == 'sentinel':
                peer = retval[1]
            else:
                break

    except KeyboardInterrupt:
        logger.warning("user stop")
