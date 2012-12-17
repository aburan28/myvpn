import os
from zlib import compress, decompress
from struct import pack, unpack
from argparse import ArgumentTypeError
from subprocess import call, check_call
from wsgiref.simple_server import make_server
import logging
import urlparse
import socket
import threading

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

    app = make_app(tun)
    host, port = args.bind.split(':')
    port = int(port)
    httpd = make_server(host, port, app)
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
    f.read(len(FAKE_HEAD))
    while True:
        data_len = unpack('H', f.read(2))[0]
        data = f.read(data_len)
        data = decrypt(data)
        yield data


def read_tun(tun):
    yield FAKE_HEAD
    while True:
        data = os.read(tun.fd, 1500)
        data = encrypt(data)
        yield pack('H', len(data)) + data


def make_app(tun):
    def app(environ, start_response):
        method = environ['REQUEST_METHOD']
        if method == 'GET':
            start_response('200 OK', [('Content-Type', 'audio/mpeg')])
            for data in read_tun(tun):
                yield data

        elif method == 'POST':
            f = environ['wsgi.input']
            for data in read_connection(f):
                os.write(tun.fd, data)


