"""vista-clients: General-purpose Python clients for VistA systems.

Provides two sub-packages:

- ``vista_clients.rpc`` — RPC Broker client (XWB wire protocol over TCP)
- ``vista_clients.terminal`` — Interactive terminal client (SSH + expect engine)

Install with ``pip install vista-clients`` for the RPC module only,
or ``pip install vista-clients[terminal]`` to include SSH terminal support.
"""

from importlib.metadata import version

__version__: str = version("vista-clients")
