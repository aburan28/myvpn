import sys
from subprocess import check_call, Popen, call
from commands import getoutput
import atexit
import logging
from socket import gethostbyname
from time import sleep

logger = logging.getLogger(__name__)

def populate_argument_parser(parser):
    server_mode = '--server' in sys.argv

    if not server_mode:
        parser.add_argument('host')
        parser.add_argument('--path', default='myvpn', help="path to myvpn on server")
        parser.add_argument('--default-gateway', action='store_true',
                            help="use vpn as default gateway")
        parser.add_argument('--up',
                            help="script to run at connection")
        parser.add_argument('--down',
                            help="script to run at connection closed")

    parser.add_argument('--server', action='store_true', help="server mode")
    parser.add_argument('-w', dest='tun')
    parser.add_argument('client_tun_ip', nargs='?', default='192.168.5.2')
    parser.add_argument('server_tun_ip', nargs='?', default='192.168.5.1')
    parser.add_argument('-l', '--login-name')
    parser.add_argument('-i', '--identify-file')


def main(args):
    if args.server:
        return server(args)

    host_ip = gethostbyname(args.host)
    local_tun, remote_tun = ['tun%s' % x for x in args.tun.split(':')]

    ssh_cmd = ['ssh', '-w', args.tun]
    if args.login_name:
        ssh_cmd += ['-l', args.login_name]
    if args.identify_file:
        ssh_cmd += ['-i', args.identify_file]
    ssh_cmd.append(args.host)
    remote_cmd = ['sudo', args.path, 'ssh', '--server', '-w', args.tun,
                  args.client_tun_ip, args.server_tun_ip]
    cmd = ssh_cmd + remote_cmd
    ssh_p = Popen(cmd)
    atexit.register(ssh_p.terminate)

    while True:
        retval = call(['ifconfig', local_tun, args.client_tun_ip,
                       args.server_tun_ip, 'up'],
                      stderr=None if args.verbose else open('/dev/null', 'w'))
        if retval == 0:
            break
        sleep(1)

    gateway = get_default_gateway()

    if args.down:
        atexit.register(on_down, args.down)

    call(['route', 'delete', host_ip+'/32'])
    check_call(['route', 'add', host_ip+'/32', gateway])
    atexit.register(call, ['route', 'delete', host_ip+'/32'])

    if args.default_gateway:
        logger.info("set default gateway")
        call(['route', 'delete', 'default'])
        check_call(['route', 'add', 'default', args.server_tun_ip])
        atexit.register(restore_gateway, gateway)

    if args.up:
        logger.info("Run up script")
        check_call(args.up)

    ssh_p.wait()

def restore_gateway(gateway):
    logger.info("restore gateway to %s", gateway)
    call(['route', 'delete', 'default'])
    call(['route', 'add', 'default', gateway])

def server(args):
    local_tun, remote_tun = ['tun%s' % x for x in args.tun.split(':')]
    check_call(['ifconfig', remote_tun, args.server_tun_ip, 'pointopoint',
                args.client_tun_ip, 'up'])
    netseg = '.'.join(args.server_tun_ip.split('.')[:3] + ['0/24'])
    call(['iptables', '-t', 'nat', '-D', 'POSTROUTING', '-s', netseg, '-j',
          'MASQUERADE'])
    check_call(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-s', netseg,
                '-j', 'MASQUERADE'])


def get_default_gateway():
    output = getoutput("netstat -nr | grep default | head -n1 | awk '{ print $2 }'")
    gateway = output.strip()
    return gateway


def on_down(script):
    logger.info("Run down script")
    call([script], stdout=open('/dev/null', 'w'))
