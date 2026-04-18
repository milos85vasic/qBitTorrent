# Plugin Execution

Each tracker plugin runs as a subprocess following the qBittorrent nova3
contract (`url`, `name`, `supported_categories`, `search()`,
`download_torrent()`).

```mermaid
{% include-markdown "../../../docs/architecture/plugin-execution.mmd" %}
```
