from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Opportunity:
    source: str
    title: str
    url: str
    agency: str = ""
    notice_id: str = ""
    notice_type: str = ""
    posted: Optional[date] = None
    deadline: Optional[date] = None
    description: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    software: list[str] = field(default_factory=list)  # reasons it is software work; empty = not software

    @property
    def key(self) -> str:
        raw = f"{self.source}|{self.notice_id or self.url}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["key"] = self.key
        d["is_software"] = bool(self.software)
        d["posted"] = self.posted.isoformat() if self.posted else None
        d["deadline"] = self.deadline.isoformat() if self.deadline else None
        return d
