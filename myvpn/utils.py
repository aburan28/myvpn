import os
import logging
from select import select
from collections import deque

from myvpn.consts import DEFAULT_PORT

logger = logging.getLogger(__name__)

def get_platform():
    return os.uname()[0].lower()

def populate_common_argument_parser(parser):
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help="TCP port [default: %(default)s]")
    platform = get_platform()
    default_device = '/dev/tun5' if platform == 'darwin' else '/dev/net/tun'
    parser.add_argument('--device', default=default_device,
                        help="TUN device [default: %(default)s]")


def proxy(tun_fd, sock, peer):
    inq, outq = deque(), deque()
    while 1:
        r, w = select([tun_fd, sock], [tun_fd, sock], [])

        for fd in r:
            if fd == tun_fd:
                data = os.read(tun_fd, 1500)
                logger.debug("> %dB", len(data))
                outq.append(data)

            else:
                data, remote_addr = sock.recvfrom(1504)
                if remote_addr != peer:
                    logger.warning("Got packet from %s:%i instead of %s:%i" %
                                (remote_addr + peer))
                    continue

                data_len = int(data[:4], 16)
                logger.debug("< %dB", data_len)
                data = data[4:]
                if len(data) != data_len:
                    logger.warning("packet broken, expect %dB, got %dB", data_len, len(data))
                    continue

                inq.append(data)

        for fd in w:
            if fd == tun_fd and inq:
                data = inq.popleft()
                logger.debug("<< %dB", len(data))
                os.write(tun_fd, data)

            elif fd == sock and outq:
                data = outq.popleft()
                logger.debug(">> %dB", len(data))
                sock.sendto('%04x' % len(data) + data, peer)
