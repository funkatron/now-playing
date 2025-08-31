import logging
from typing import Optional


class OBSClient:
    def __init__(self, host: str = "localhost", port: int = 4455, password: Optional[str] = None) -> None:
        self.host = host
        self.port = port
        self.password = password or "tH3NSzMaqHHaWExM"

    def update_image_source(self, source_name: str, file_path: str) -> None:
        from obswebsocket import obsws, requests  # type: ignore

        ws = obsws(self.host, self.port, self.password)
        ws.connect()
        try:
            ws.call(
                requests.SetInputSettings(
                    inputName=source_name,
                    inputSettings={
                        "file": file_path,
                    },
                )
            )
        finally:
            try:
                ws.disconnect()
            except Exception as e:  # pragma: no cover
                logging.debug(f"OBS disconnect issue: {e}")


