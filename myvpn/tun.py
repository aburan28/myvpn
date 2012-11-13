import os
import sys
from fcntl import ioctl
import struct
import logging
from subprocess import check_call

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001

logger = logging.getLogger(__name__)

class Tun(object):
    def __init__(self, ip, device='/dev/net/tun', mtu=1300):
        self.ip = ip
        self.device = device
        self.mtu = mtu

    def open(self):
        self.fd = os.open(self.device, os.O_RDWR)
        if sys.platform.startswith('linux'):
            iface = ioctl(self.fd, TUNSETIFF, struct.pack('16sH', 'tun%d', IFF_TUN))
            self.ifname = iface[:16].strip('\0')
        else:
            self.ifname = self.device.split('/')[-1]
        logger.info("%s open", self.ifname)
        check_call(['ip', 'link', 'set', self.ifname, 'up'])
        check_call(['ip', 'link', 'set', self.ifname, 'mtu', str(self.mtu)])
        check_call(['ip', 'addr', 'add', self.ip, 'dev', self.ifname])

    def close(self):
        os.close(self.fd)
        del self.fd
