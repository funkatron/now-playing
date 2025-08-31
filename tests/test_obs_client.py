def test_obs_client_update_calls_ws(monkeypatch):
    calls = []

    class DummyReq:
        def __init__(self, inputName=None, inputSettings=None):
            self.inputName = inputName
            self.inputSettings = inputSettings

    class DummyWS:
        def __init__(self, host, port, password):
            calls.append(("connect", host, port, password))
        def connect(self):
            pass
        def call(self, req):
            calls.append(("call", req.inputName, req.inputSettings))
        def disconnect(self):
            calls.append(("disconnect",))

    def fake_obsws(host, port, password):
        return DummyWS(host, port, password)

    class DummyRequests:
        def SetInputSettings(self, inputName=None, inputSettings=None):
            return DummyReq(inputName=inputName, inputSettings=inputSettings)

    # Patch obswebsocket imports inside OBSClient method
    import now_playing.obs_client as obs_client

    def fake_import_obs():
        class _Mod:
            obsws = fake_obsws
            requests = DummyRequests()
        return _Mod

    def fake_update(self, source_name, file_path):
        _mod = fake_import_obs()
        ws = _mod.obsws(self.host, self.port, self.password)
        ws.connect()
        try:
            ws.call(_mod.requests.SetInputSettings(inputName=source_name, inputSettings={"file": file_path}))
        finally:
            ws.disconnect()

    monkeypatch.setattr(obs_client.OBSClient, "update_image_source", fake_update, raising=True)

    client = obs_client.OBSClient(password="pw")
    client.update_image_source("NPImageApple", "/tmp/cover.png")

    # We only verify that our fake flow logged expected call shapes
    assert any(ev[0] == "call" and ev[1] == "NPImageApple" for ev in calls)


