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

from myvpn.tun import Tun
from myvpn.utils import get_platform

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
        pass

    class Handler(StreamRequestHandler):
        def handle(self):
            method = self.rfile.readline().split()[0]
            while self.rfile.readline().strip():
                pass
            if method == 'GET':
                self.wfile.write('HTTP/1.1 200 OK\r\n')
                self.wfile.write('Server: python\r\n')
                self.wfile.write('Content-Type: audio/mpeg\r\n')
                self.wfile.write('\r\n')
                for data in read_tun(tun):
                    self.wfile.write(data)
                    self.wfile.flush()

            elif method == 'POST':
                for data in read_connection(self.rfile):
                    os.write(tun.fd, data)

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

    def get():
        sock = socket.socket()
        sock.connect((host, port))
        sock.sendall('GET /%s HTTP/1.1\r\n' % url.path)
        sock.sendall('Host: %s\r\n' % url.netloc)
        sock.sendall('Accept: */*\r\n')
        sock.sendall('\r\n')

        f = sock.makefile('r', 0)
        for data in read_connection(f):
            os.write(tun.fd, data)

    def post():
        sock = socket.socket()
        sock.connect((host, port))
        sock.sendall('POST /%s HTTP/1.1\r\n' % url.path)
        sock.sendall('Host: %s\r\n' % url.netloc)
        sock.sendall('Accept: */*\r\n')
        sock.sendall('\r\n')

        for data in read_tun(tun):
            sock.sendall(data)

    post()
    return

    t1 = threading.Thread(target=get)
    t2 = threading.Thread(target=post)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def encrypt(data):
    return compress(data)[::-1]

def decrypt(data):
    return decompress(data[::-1])

def read_connection(f):
    data = f.read(len(FAKE_HEAD))
    if data != FAKE_HEAD:
        return

    while True:
        data_len = f.read(2)
        if not data_len:
            break

        data_len = unpack('H', data_len)[0]
        data = f.read(data_len)
        if len(data) < data_len:
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


