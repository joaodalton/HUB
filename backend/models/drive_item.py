from dataclasses import dataclass


@dataclass
class DriveItem:
    id: str
    name: str
    mimeType: str
    webViewLink: str
    iconLink: str | None = None
    modifiedTime: str | None = None
