import os
import time
from zlib import compress, decompress
from struct import pack, unpack
from argparse import ArgumentTypeError
from subprocess import call, check_call
from SocketServer import TCPServer, ThreadingMixIn, StreamRequestHandler
import logging
import urlparse
import socket
import threading
import errno
import atexit

from .tun import Tun
from .utils import get_platform, add_route, get_default_gateway, \
        restore_gateway

FAKE_HEAD = b'ID3\x02\x00\x00\x00\x00'

logger = logging.getLogger(__name__)

def ip(s):
    try:
        segs = [int(x) for x in s.split('.')]
        if len(segs) != 4:
            raise ValueError
        if not all(0 <= seg <= 255 for seg in segs):
            raise ValueError
        return s
    except ValueError:
        raise ArgumentTypeError("%r is not a valid IP address" % s)


def populate_argument_parser(parser):
    parser.add_argument('--mode', choices=['server', 'client'],
                        default='client')
    platform = get_platform()
    default_device = '/dev/tun5' if platform == 'darwin' else '/dev/net/tun'
    parser.add_argument('--device', default=default_device, help="TUN device")
    parser.add_argument('--ip', type=ip)
    parser.add_argument('--peer-ip', type=ip)

    server_group = parser.add_argument_group('server mode only')
    server_group.add_argument('-b', '--bind', default='127.0.0.1:2504',
                              help="interface to listen")

    client_group = parser.add_argument_group('client mode only')
    client_group.add_argument('--url', help="server url")
    client_group.add_argument('--default-gateway', action='store_true',
                              help="use vpn as default gateway")
    client_group.add_argument('--up', help="script to run at connection")
    client_group.add_argument('--down', help="script to run at disconnection")


def main(args):
    tun = Tun(args.device, args.ip, args.peer_ip)
    tun.open()

    if args.mode == 'server':
        server_main(args, tun)
    else:
        client_main(args, tun)


def server_main(args, tun):
    netseg = '.'.join(args.ip.split('.')[:3] + ['0/24'])
    call(['iptables', '-t', 'nat', '-D', 'POSTROUTING', '-s', netseg, '-j', 'MASQUERADE'])
    check_call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-s', netseg, '-j', 'MASQUERADE'])

    host, port = args.bind.split(':')
    port = int(port)

    class HTTPServer(ThreadingMixIn, TCPServer):
        allow_reuse_address = True
        daemon_threads = True

    class Handler(StreamRequestHandler):
        def handle(self):
            line = self.rfile.readline().strip()
            logger.info("%s: %s", self.client_address, line)
            try:
                method = line.split()[0]
                while self.rfile.readline().strip():
                    pass
                if method == 'GET':
                    self.wfile.write('HTTP/1.1 200 OK\r\n')
                    self.wfile.write('Server: python\r\n')
                    self.wfile.write('Content-Type: audio/mpeg\r\n')
                    self.wfile.write('\r\n')
                    for data in read_tun(tun):
                        logger.debug('> %dB', len(data))
                        self.wfile.write(data)
                        self.wfile.flush()

                elif method == 'POST':
                    for data in read_connection(self.rfile):
                        logger.debug('< %dB', len(data))
                        os.write(tun.fd, data)

            finally:
                logger.info("%s %s: disconnected", self.client_address, method)

    httpd = HTTPServer((host, port), Handler)
    logger.warning("Serving on %s:%d", host, port)
    httpd.serve_forever()


def client_main(args, tun):
    url = urlparse.urlparse(args.url)
    if ':' in url.netloc:
        host, port = url.netloc.split(':')
        port = int(port)
    else:
        host, port = url.netloc, 80

    host_ip = socket.gethostbyname(host)

    def get():
        sock = socket.socket()
        sock.connect((host, port))
        logger.info("GET %s", args.url)
        sock.sendall('GET %s HTTP/1.1\r\n' % url.path)
        sock.sendall('Host: %s\r\n' % url.netloc)
        sock.sendall('Accept: */*\r\n')
        sock.sendall('\r\n')

        f = sock.makefile('r', 0)
        while f.readline().strip():
            # read until blank line
            pass

        for data in read_connection(f):
            logger.debug('< %dB', len(data))
            os.write(tun.fd, data)

        logger.warning("quit get")

    def post():
        sock = socket.socket()
        sock.connect((host, port))
        logger.info("POST %s", args.url)
        sock.sendall('POST %s HTTP/1.1\r\n' % url.path)
        sock.sendall('Host: %s\r\n' % url.netloc)
        sock.sendall('Accept: */*\r\n')
        sock.sendall('\r\n')

        for data in read_tun(tun):
            logger.debug('> %dB', len(data))
            sock.sendall(data)

        logger.warning("quit post")


    t1 = threading.Thread(target=get)
    t1.setDaemon(True)
    t2 = threading.Thread(target=post)
    t2.setDaemon(True)
    t1.start()
    t2.start()

    gateway = get_default_gateway()

    if args.down:
        atexit.register(on_down, args.down)

    add_route(host_ip + '/32', gateway)

    if args.default_gateway:
        logger.info("set default gateway")
        call(['route', 'delete', 'default'])
        check_call(['route', 'add', 'default', args.peer_ip])
        atexit.register(restore_gateway)

    if args.up:
        logger.info("Run up script")
        check_call(args.up)

    try:
        while t1.is_alive() and t2.is_alive():
            time.sleep(5)
    except KeyboardInterrupt:
        pass

def encrypt(data):
    return compress(data)[::-1]

def decrypt(data):
    return decompress(data[::-1])

def read_connection(f):
    data = f.read(len(FAKE_HEAD))
    if data != FAKE_HEAD:
        logger.debug("read fake head: %r", data)
        return
    logger.debug("got fake head")

    while True:
        data_len = f.read(2)
        if not data_len:
            logger.debug("read data len: %dB", len(data))
            break

        data_len = unpack('H', data_len)[0]
        data = f.read(data_len)
        if len(data) < data_len:
            logger.debug("read data (expect %dB): %dB", data_len, len(data))
            break

        data = decrypt(data)
        yield data


def read_tun(tun):
    yield FAKE_HEAD
    while True:
        try:
            data = os.read(tun.fd, 1500)
        except OSError, e:
            if e.errno == errno.EAGAIN:
                time.sleep(1)
                continue
        data = encrypt(data)
        yield pack('H', len(data)) + data


def on_down(script):
    logger.info("Run down script")
    call([script], stdout=open('/dev/null', 'w'))
