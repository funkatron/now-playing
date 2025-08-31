import types
import sys


def test_obs_client_real_method_via_sys_modules(monkeypatch):
    events = []

    class DummyReq:
        def __init__(self, inputName=None, inputSettings=None):
            self.inputName = inputName
            self.inputSettings = inputSettings

    class DummyRequests:
        def SetInputSettings(self, inputName=None, inputSettings=None):
            return DummyReq(inputName=inputName, inputSettings=inputSettings)

    class DummyWS:
        def __init__(self, host, port, password):
            events.append(("init", host, port, password))
        def connect(self):
            events.append(("connect",))
        def call(self, req):
            events.append(("call", req.inputName, req.inputSettings))
        def disconnect(self):
            events.append(("disconnect",))

    fake_module = types.ModuleType("obswebsocket")
    fake_module.obsws = lambda host, port, password: DummyWS(host, port, password)
    fake_module.requests = DummyRequests()

    monkeypatch.setitem(sys.modules, "obswebsocket", fake_module)

    from now_playing.obs_client import OBSClient

    client = OBSClient(password="pw")
    client.update_image_source("NPImageApple", "/tmp/c.png")

    # Ensure the call event happened with expected payload
    assert any(e[0] == "call" and e[1] == "NPImageApple" and e[2]["file"] == "/tmp/c.png" for e in events)


