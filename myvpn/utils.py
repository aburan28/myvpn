import os
import logging
from select import select

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


def encrypt(data):
    return data[::-1]

def decrypt(data):
    return data[::-1]

def proxy(tun_fd, sock, peer, break_on_packet=None):
    while 1:
        fd = select([tun_fd, sock], [], [])[0][0]
        if fd == tun_fd:
            data = os.read(tun_fd, 1500)
            data = encrypt(data)
            logger.debug("> %dB", len(data))
            sock.sendto('%04x' % len(data) + data, peer)
        else:
            data, remote_addr = sock.recvfrom(1504)
            if remote_addr != peer:
                if data == break_on_packet:
                    return 'sentinel', remote_addr
                else:
                    logger.warning("Got packet from %s:%i instead of %s:%i" %
                                (remote_addr + peer))
                    continue

            data_len = int(data[:4], 16)
            data = data[4:]
            if len(data) != data_len:
                logger.warning("Got broken packet. expect %dB, got %dB", data_len, len(data))
                continue
            logger.debug("< %dB", data_len)
            data = decrypt(data)
            os.write(tun_fd, data)
