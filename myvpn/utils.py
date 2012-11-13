import os
import logging
from select import select

from myvpn.consts import DEFAULT_PORT

logger = logging.getLogger(__name__)

def populate_common_argument_parser(parser):
    parser.add_argument('--ip', required=True)
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help="TCP port [default: %(default)s]")
    parser.add_argument('--device', default='/dev/net/tun',
                        help="TUN device [default: %(default)s]")


def proxy(tun, sock):
    while 1:
        fd = select([tun.fd, sock], [], [])[0][0]
        if fd == tun.fd:
            data = os.read(tun.fd, 1500)
            logger.debug("> %dB", len(data))
            sock.sendall(os.read(tun.fd, 1500))
        else:
            data = sock.recv(1500)
            logger.debug("< %dB", len(data))
            os.write(tun.fd, data)
