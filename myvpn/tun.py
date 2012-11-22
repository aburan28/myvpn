import os
from fcntl import ioctl
import struct
import logging
from subprocess import check_call

from .utils import get_platform

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

logger = logging.getLogger(__name__)
platform = get_platform()

class Tun(object):
    def __init__(self, device, ip, peer_ip):
        self.device = device
        self.ip = ip
        self.peer_ip = peer_ip

    def open(self):
        self.fd = os.open(self.device, os.O_RDWR)

        if platform == 'linux':
            iface = ioctl(self.fd, TUNSETIFF, struct.pack('16sH', 'tun%d', IFF_TUN|IFF_NO_PI))
            self.ifname = iface[:16].strip('\0')
            check_call(['ifconfig', self.ifname, self.ip, 'pointopoint',
                        self.peer_ip, 'up'])
        else:
            self.ifname = self.device.split('/')[-1]
            check_call(['ifconfig', self.ifname, self.ip, self.peer_ip,
                        'up'])

        logger.info("%s open", self.ifname)


    def close(self):
        os.close(self.fd)
        del self.fd
