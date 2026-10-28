"""Read-only OM-3 Wi-Fi discovery; COLOR/HSL writes are intentionally refused."""
from penf_wifi.protocol import ClientError, named, xml_root
from penf_wifi.transport import HTTPError


SUPPORTED_MODELS = frozenset({"OM-3"})


class Camera:
    def __init__(self, transport, progress=None):
        self.transport = transport
        self.progress = progress or (lambda message: None)

    def identify(self):
        self.progress("Contacting camera (read-only identification)...")
        root = xml_root(self.transport.get("get_caminfo.cgi"))
        nodes = named(root, "model")
        if root.tag.rsplit("}", 1)[-1] != "caminfo" or len(nodes) != 1:
            raise ClientError("Expected camera information with one model name")
        model = (nodes[0].text or "").strip()
        if model.upper() not in {m.upper() for m in SUPPORTED_MODELS}:
            raise ClientError(
                f"This client supports OM-3 only; camera reported {model!r}. "
                "Use camera_client.penf_wifi for PEN-F."
            )
        return {
            "model": model,
            "fields": {x.tag.rsplit("}", 1)[-1]: x.text for x in root if len(x) == 0},
        }

    def discover(self):
        info = self.identify()
        connection = xml_root(self.transport.get("get_connectmode.cgi"))
        commands = xml_root(self.transport.get("get_commandlist.cgi"))
        if commands.tag.rsplit("}", 1)[-1] != "oishare":
            raise ClientError("Expected the camera's <oishare> command list")
        advertised = [x.attrib.get("name") for x in named(commands, "cgi")]
        return {
            "camera": info,
            "connection": {
                x.tag.rsplit("}", 1)[-1]: x.text
                for x in connection.iter()
                if len(x) == 0
            },
            "advertised_commands": advertised,
            "notes": [
                "No mode change or setting write.",
                "OM-3 stock may advertise settings-backup / partial-transfer names; "
                "this client does not implement those transfers.",
                "No HSL1 / COLOR recipe write path is claimed for stock OM-3.",
            ],
        }

    def refuse_writes(self):
        raise ClientError(
            "OM-3 COLOR/HSL recipe writes are not supported by this research client. "
            "Stock OM-3 protocol differences from PEN-F HSL1 are undocumented here; "
            "no upload path is offered."
        )

    def session(self, mode):
        self.refuse_writes()

    def snapshot(self, profile):
        self.refuse_writes()

    def apply(self, plan, state):
        self.refuse_writes()
