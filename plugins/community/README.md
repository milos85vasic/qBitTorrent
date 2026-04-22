# Community Plugins

These tracker plugins are community contributions. They are not part of the
canonical managed set and must be installed individually.

## Installation

To install a specific community plugin:

```bash
# Copy to qBittorrent engines directory
cp plugins/community/<name>.py config/qBittorrent/nova3/engines/

# Or use install-plugin.sh (add the name to the PLUGINS array first)
./install-plugin.sh <name>
```

To install all community plugins at once:

```bash
for f in plugins/community/*.py; do
    cp "$f" config/qBittorrent/nova3/engines/
done
```

## Verification

Each community plugin passes `python3 -m py_compile` syntax validation.
Run the smoke test to verify:

```bash
python3 -m pytest tests/unit/test_community_plugins_compile.py -v
```

## Adding a Community Plugin

1. Place the `.py` file in `plugins/community/`
2. Ensure it passes `python3 -m py_compile`
3. The smoke test in `tests/unit/test_community_plugins_compile.py` will
   automatically pick it up

## Promotion to Canonical

To promote a community plugin to the canonical set, it needs:

- A dedicated unit test in `tests/unit/`
- Documentation in `docs/PLUGINS.md`
- An entry in the `PLUGINS` array in `install-plugin.sh`
- Constitution amendment (see `.specify/memory/constitution.md`)
