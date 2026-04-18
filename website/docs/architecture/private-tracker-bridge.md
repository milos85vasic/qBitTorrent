# Private Tracker Bridge

The `webui-bridge.py` host process (port `7188`) forwards cookie-authenticated
download requests from qBittorrent to private trackers that refuse
container-side network access.

```mermaid
{% include-markdown "../../../docs/architecture/private-tracker-bridge.mmd" %}
```
