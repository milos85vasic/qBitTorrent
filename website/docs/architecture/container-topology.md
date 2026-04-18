# Container Topology

Two containers plus one host process make up the runtime. The merge service
and download proxy share a single container; qBittorrent runs in its own
LinuxServer.io container; `webui-bridge.py` runs on the host for private
tracker cookie forwarding.

```mermaid
{% include-markdown "../../../docs/architecture/container-topology.mmd" %}
```
