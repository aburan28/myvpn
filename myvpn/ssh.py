from subprocess import check_call, Popen, call
from commands import getoutput
import atexit
import logging
from socket import gethostbyname

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    parser.add_argument('host')
    parser.add_argument('-w', dest='tun')
    parser.add_argument('path', help="path to myvpn on server")
    parser.add_argument('--server', action='store_true', help="server mode")
    parser.add_argument('client-tun-ip', nargs='?', default='10.1.1.1')
    parser.add_argument('server-tun-ip', nargs='?', default='10.1.1.2')
    parser.add_argument('tun-netmask', nargs='?', default='255.255.255.252')
    parser.add_argument('--default-gateway', action='store_true',
                        help="use vpn as default gateway")
    parser.add_argument('--up',
                        help="script to run at connection")
    parser.add_argument('--down',
                        help="script to run at connection closed")


def main(args):
    if args.server:
        return server(args)

    host_ip = gethostbyname(args.host)
    local_tun, remote_tun = ['tun%s' % x for x in args.tun.split(':')]

    ssh_p = Popen(['ssh', '-w', args.tun, host_ip, args.path, 'ssh',
                   '--server', '-w', args.tun, args.client_tun_ip,
                   args.server_tun_ip, args.tun_netmask])
    check_call(['ifconfig', local_tun, args.client_tun_ip, args.server_tun_ip,
                'netmask', args.tun_netmask])

    gateway = get_default_gateway()

    if args.down:
        atexit.register(on_down, args.down, server_ip=args.server_tun_ip,
                        restore_gateway=gateway if args.default_gateway else None)

    call(['route', 'delete', host_ip+'/32'])
    check_call(['route', 'add', host_ip+'/32', gateway])

    if args.default_gateway:
        logger.info("set default gateway")
        call(['route', 'delete', 'default'])
        check_call(['route', 'add', 'default', args.tun_server_tun_ip])

    if args.up:
        logger.info("Run up script")
        check_call(args.up)

    ssh_p.wait()


def server(args):
    local_tun, remote_tun = ['tun%s' % x for x in args.tun.split(':')]
    check_call(['ifconfig', remote_tun, args.server_tun_ip,
                args.client_tun_ip, 'netmask', args.tun_netmask])
    netseg = '.'.join(args.server_tun_ip.split('.')[:3] + ['0/24'])
    call(['iptables', '-t', 'nat', '-D', 'POSTROUTING', '-s', netseg, '-j',
          'MASQUERADE'])
    check_call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-s', netseg,
                '-j', 'MASQUERADE'])


def get_default_gateway():
    output = getoutput("netstat -nr | grep default | head -n1 | awk '{ print $2 }'")
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
