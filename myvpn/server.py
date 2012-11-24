import logging
from SocketServer import TCPServer, BaseRequestHandler
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

    server = TCPServer(('0.0.0.0', args.port), MyHandlerFactory(tun))
    server.serve_forever()


def MyHandlerFactory(tun):
    class MyHandler(BaseRequestHandler):
        def handle(self):
            data = self.request.recv(len(MAGIC_WORD))
            if data != MAGIC_WORD:
                logger.warning("bad magic word for %s:%i" % self.client_address)
                return

            logger.info("client connected from %s:%i" % self.client_address)
            self.request.send(MAGIC_WORD)

            proxy(tun.fd, self.request)

    return MyHandler
