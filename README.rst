============
MyVPN
============

有两种工作模式，ssh tunnel 和 http tunnel。

自动完成路由配置。可设定成为默认路由。

可在连接成功/关闭时执行up/down script （比如配合 `chnroute`_ )。


目前支持 Linux 作为服务端，Mac OS X作为客户端。

.. _chnroute: http://code.google.com/p/chnroutes/

ssh tunnel
==========

支持指定ssh key，免输远端password。


Installation
------------

在服务器和客户端都安装 myvpn 脚本。

服务端 sshd_config 需要打开 PermitTunnel::

  PermitTunnel yes

在客户端运行::

  sudo myvpn ssh server.com -w 3:4 --path /path/to/bin/myvpn/on/server

检查是否可 ping 通::

  ping 192.168.5.1

详细参数可::

  myvpn ssh -h


http tunnel
===========

通过伪装mp3上传和下载的http连接，基于tun设备建立tunnel。

Installation
------------

在服务器和客户端都安装 myvpn 脚本。

在服务端运行::

  sudo myvpn http --mode server --ip 192.168.5.1 --peer-ip 192.168.5.2 -b 0.0.0.0:82

在客户端运行::

  sudo myvpn http --ip 192.168.5.2 --peer-ip 192.168.5.1 --url http://your.server:82/

检查是否可 ping 通::

  ping 192.168.5.1

详细参数可::

  myvpn http -h


