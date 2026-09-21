"""Flags opportunities that are fundamentally software work: greenfield development,
brownfield modernization/sustainment, or software-as-the-deliverable (apps, platforms,
firmware, data/ML systems). Applied centrally in main.collect to every source."""
from __future__ import annotations

import re

from .models import Opportunity

# Phrases (matched at word starts, case-insensitive) that describe software work itself.
# Deliberately excludes "IT" / "systems" / "engineering" alone, which cover hardware and
# generic support far more often than code.
SOFTWARE_KEYWORDS = [
    "software",
    "application development",
    "app development",
    "application modernization",
    "software modernization",
    "system modernization",
    "systems modernization",
    "it modernization",
    "legacy system",
    "devsecops",
    "devops",
    "agile development",
    "coding",
    "programming",
    "firmware",
    "middleware",
    "api",
    "microservice",
    "cloud native",
    "cloud migration",
    "saas",
    "platform as a service",
    "web application",
    "mobile application",
    "mission software",
    "flight software",
    "ground software",
    "ground system software",
    "command and control software",
    "c2 software",
    "battle management",
    "data platform",
    "data pipeline",
    "machine learning",
    "artificial intelligence",
    "algorithm development",
    "simulation software",
    "digital engineering",
    "digital twin",
    "model-based systems engineering",
    "mbse",
    "software factory",
    "software sustainment",
    "software maintenance",
    "software support",
    "software license",
    "cybersecurity software",
    "user interface",
    "database",
    "open source",
    "kubernetes",
    "containerization",
]

# NAICS codes whose primary output is software or software services.
SOFTWARE_NAICS = {
    "511210": "software publishers",
    "513210": "software publishers",
    "518210": "computing infrastructure / data processing / hosting",
    "541511": "custom computer programming services",
    "541512": "computer systems design services",
    "541519": "other computer related services",
}

# PSC codes (exact code or prefix) for software development, sustainment and licenses.
SOFTWARE_PSC = {
    "7030": "IT software",
    "D302": "ADP systems development",
    "D306": "ADP systems analysis",
    "D307": "automated information system design and integration",
    "D308": "programming services",
    "D318": "integrated hardware/software/services solution",
    "D319": "annual software maintenance",
    "D399": "other ADP and telecom services",
    "DA": "IT applications (development, support, SaaS)",
    "DB10": "compute as a service",
    "DF": "IT management support",
    "DG": "IT platform / platform-as-a-service",
}

_PSC_RE = re.compile(r"\bPSC\s+([A-Z0-9]{1,4})\b")
_NAICS_RE = re.compile(r"\bNAICS\s+(\d{6})\b")


def software_tags(opp: Opportunity) -> list[str]:
    """Reasons an opportunity counts as software work; empty when it does not."""
    reasons: list[str] = []
    text = f"{opp.title} {opp.description} {opp.summary}".lower()

    m = _NAICS_RE.search(opp.description)
    if m and m.group(1) in SOFTWARE_NAICS:
        reasons.append(f"NAICS {m.group(1)} ({SOFTWARE_NAICS[m.group(1)]})")
    m = _PSC_RE.search(opp.description)
    if m:
        code = m.group(1)
        for prefix, label in SOFTWARE_PSC.items():
            if code == prefix or (len(prefix) < 4 and code.startswith(prefix)):
                reasons.append(f"PSC {code} ({label})")
                break

    for kw in SOFTWARE_KEYWORDS:
        tail = r"\b" if len(kw) <= 4 else ""
        if re.search(rf"\b{re.escape(kw)}{tail}", text):
            reasons.append(kw)
    return reasons


def is_software(opp: Opportunity) -> bool:
    return bool(software_tags(opp))
