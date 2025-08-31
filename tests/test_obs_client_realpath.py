def test_obs_client_update_calls_with_expected_args(monkeypatch):
    events = []

    class DummyReq:
        def __init__(self, inputName=None, inputSettings=None):
            self.inputName = inputName
            self.inputSettings = inputSettings

    class DummyWS:
        def __init__(self, host, port, password):
            events.append(("init", host, port, password))
        def connect(self):
            events.append(("connect",))
        def call(self, req):
            events.append(("call", req.inputName, req.inputSettings))
        def disconnect(self):
            events.append(("disconnect",))

    # Provide fake obswebsocket module bindings used by obs_client
    import now_playing.obs_client as obs_client

    def fake_obsws(host, port, password):
        return DummyWS(host, port, password)

    class FakeRequests:
        def SetInputSettings(self, inputName=None, inputSettings=None):
            return DummyReq(inputName=inputName, inputSettings=inputSettings)

    # Monkeypatch inside the method scope by replacing the whole method to use our fakes
    def fake_update(self, source_name, file_path):
        class _mod:
            obsws = fake_obsws
            requests = FakeRequests()
        ws = _mod.obsws(self.host, self.port, self.password)
        ws.connect()
        try:
            ws.call(_mod.requests.SetInputSettings(inputName=source_name, inputSettings={"file": file_path}))
        finally:
            ws.disconnect()

    monkeypatch.setattr(obs_client.OBSClient, "update_image_source", fake_update, raising=True)

    client = obs_client.OBSClient(password="pw")
    client.update_image_source("NPImageSpotify", "/abs/path/art.png")

    assert any(ev[0] == "call" and ev[1] == "NPImageSpotify" and ev[2]["file"] == "/abs/path/art.png" for ev in events)


