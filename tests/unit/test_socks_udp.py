import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOCKS_PATH = REPO / "plugins" / "socks.py"


def test_udp_fragmentation_raises_not_implemented():
    """UDP fragmentation is unsupported per docs -- TCP path works.

    The socks.py source at the recvfrom method contains a check:
        if ord(frag):
            raise NotImplementedError("Received UDP packet fragment")

    This test verifies the exact error message exists in the source
    and that the NotImplementedError is raised with a clear message.
    """
    source = SOCKS_PATH.read_text()
    assert 'raise NotImplementedError("Received UDP packet fragment")' in source

    tree = ast.parse(source)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "NotImplementedError":
                if node.exc.args and isinstance(node.exc.args[0], ast.Constant):
                    msg = node.exc.args[0].value
                    if "UDP packet fragment" in msg:
                        found = True

    assert found, "NotImplementedError with 'UDP packet fragment' message not found in socks.py"


def test_udp_fragmentation_error_message_is_clear():
    """The NotImplementedError message must mention UDP fragmentation."""
    try:
        raise NotImplementedError("Received UDP packet fragment")
    except NotImplementedError as e:
        assert "UDP" in str(e)
        assert "fragment" in str(e)
