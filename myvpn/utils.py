import os
import logging
from threading import Thread
from subprocess import call, check_call, Popen, PIPE
import atexit

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

def proxy(tun_fd, sock):
    t1 = Thread(target=copy_fd_to_socket, args=(tun_fd, sock))
    t1.setDaemon(True)
    t1.start()

    copy_socket_to_fd(sock, tun_fd)

    t1.join()

def copy_fd_to_socket(fd, sock):
    while 1:
        data = os.read(fd, 1500)
        data = encrypt(data)
        logger.debug("> %dB", len(data))
        sock.sendall('%04x' % len(data) + data)

def copy_socket_to_fd(sock, fd):
    while 1:
        data_len = int(sock.recv(4), 16)
        data = ''
        while len(data) < data_len:
            data += sock.recv(data_len - len(data))
        logger.debug("< %dB", data_len)
        data = decrypt(data)
        os.write(fd, data)


def add_route(net, gateway):
    call(['route', 'delete', net])
    check_call(['route', 'add', net, gateway])
    atexit.register(call, ['route', 'delete', net])


def get_default_gateway():
    p = Popen(['scutil'], stdin=PIPE, stdout=PIPE)
    output = p.communicate('open\nget State:/Network/Global/IPv4\nd.show\nquit\n')[0]
    for line in output.splitlines():
        if 'Router' in line:
            gateway = line.split('Router : ')[-1]
            break
    return gateway


def restore_gateway():
    gateway = get_default_gateway()
    logger.info("restore gateway to %s", gateway)
    call(['route', 'delete', 'default'])
    call(['route', 'add', 'default', gateway])
