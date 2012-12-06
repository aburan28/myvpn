============
MyVPN
============

通过 ssh tunnel device forwarding 构建VPN。自动完成路由配置。可设定成为默认路由。

可在连接成功/关闭时执行up/down script （比如配合 `chnroute`_ )。

支持指定ssh key，免输远端password。

目前支持 Linux 作为服务端，Mac OS X作为客户端。

.. _chnroute: http://code.google.com/p/chnroutes/


Installation
============

在服务器和客户端都安装myssh脚本。

服务端 sshd_config 需要打开 PermitTunnel::

  PermitTunnel yes

在客户端运行::

  sudo myvpn ssh server.com -w 3:4 --path /path/to/bin/myvpn/on/server

检查是否可 ping 通::

  ping 192.168.5.1

详细参数可::

  myvpn ssh -h
