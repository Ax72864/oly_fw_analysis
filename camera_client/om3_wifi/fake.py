"""Explicit OM-3 Wi-Fi simulation for unit/loopback tests; no network I/O."""
from penf_wifi.transport import HTTPError, TransportError


class FakeOm3Camera:
    """Independent HTTP edge model for OM-3 discovery; does not emulate firmware."""

    def __init__(self, model="OM-3", remote=True):
        self.model = model
        self.remote = remote
        self.calls = []
        # Names observed in OM-3 protocol descriptions; presence is not a transfer implementation.
        self.command_names = [
            "get_caminfo",
            "switch_cammode",
            "get_camprop",
            "get_connectmode",
            "exec_takesettingbackup",
            "exec_partialtransfer",
        ]

    def get(self, endpoint, params=None):
        params = params or {}
        self.calls.append((endpoint, params.copy()))
        if endpoint == "get_caminfo.cgi":
            return (
                f"<caminfo><model>{self.model}</model>"
                f"<MISOAExpComp>available</MISOAExpComp></caminfo>"
            ).encode()
        if endpoint == "get_connectmode.cgi":
            return b"<connectmode><mode>private</mode></connectmode>"
        if endpoint == "get_commandlist.cgi":
            body = "".join(f'<cgi name="{name}"/>' for name in self.command_names)
            return f"<oishare>{body}</oishare>".encode()
        if endpoint == "switch_cammode.cgi":
            self.remote = params.get("mode") == "rec"
            return b""
        if endpoint in ("get_mcon.cgi", "set_mcon.cgi"):
            raise TransportError(
                "OM-3 FakeOm3Camera does not model mcon; research client refuses writes"
            )
        if not self.remote:
            raise HTTPError(520, endpoint)
        raise AssertionError(endpoint)
