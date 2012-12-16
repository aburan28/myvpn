import sys
from socket import socket, gethostbyname
import logging
from commands import getoutput
from subprocess import call, check_call
import atexit

from myvpn.tun import Tun
from myvpn.utils import populate_common_argument_parser, proxy, get_platform
from myvpn.consts import MAGIC_WORD

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    populate_common_argument_parser(parser)
    parser.add_argument('--server', required=True)
    parser.add_argument('--ip', default='192.168.5.2')
    parser.add_argument('--peer-ip', default='192.168.5.1')
    parser.add_argument('--default-gateway', action='store_true',
                        help="use vpn as default gateway")
    parser.add_argument('--up',
                        help="script to run at connection")
    parser.add_argument('--down',
                        help="script to run at connection closed")


def main(args):
    tun = Tun(device=args.device, ip=args.ip, peer_ip=args.peer_ip)
    tun.open()

    sock = socket()
    server_ip = gethostbyname(args.server)
    logger.info("%s resolved to %s", args.server, server_ip)

    try:
        sock.connect((server_ip, args.port))
        logger.info("connected to %s:%i" % (server_ip, args.port))
        sock.send(MAGIC_WORD)
        data = sock.recv(len(MAGIC_WORD))
        if data != MAGIC_WORD:
            logger.warning("Handshake failed")
            sys.exit(2)

        logger.info("Connection with %s:%i established" % (server_ip, args.port))

        gateway = get_default_gateway()

        if args.down:
            atexit.register(on_down, args.down,
                            server_ip=server_ip,
                            restore_gateway=gateway if args.default_gateway else None)

        call(['route', 'delete', server_ip+'/32'])
        check_call(['route', 'add', server_ip+'/32', gateway])

        if args.default_gateway:
            logger.info("set default gateway")
            call(['route', 'delete', 'default'])
            check_call(['route', 'add', 'default', args.peer_ip])

        if args.up:
            logger.info("Run up script")
            check_call(args.up)

        proxy(tun.fd, sock)

    except KeyboardInterrupt:
        logger.warning("Stopped by user")


def get_default_gateway():
    platform = get_platform()
    if platform == 'darwin':
        output = getoutput("netstat -nr | grep default | head -n1 | awk '{ print $2 }'")
        gateway = output.strip()
    else:
        output = getoutput("netstat -nr | grep -e '^0.0.0.0' | head -n1 | awk '{ print $2 }'")
        gateway = output.strip()
    return gateway


def on_down(script, server_ip, restore_gateway=None):
    if restore_gateway:
        logger.info("restore gateway to %s", restore_gateway)
        call(['route', 'delete', 'default'])
        call(['route', 'add', 'default', restore_gateway])

    call(['route', 'delete', server_ip+'/32'])

    logger.info("Run down script")
    call([script])
