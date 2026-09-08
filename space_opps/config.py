"""Keywords and agency filters shared by all sources."""

SPACE_KEYWORDS = [
    "space",
    "satellite",
    "launch",
    "orbit",
    "orbital",
    "spacecraft",
    "lunar",
    "moon",
    "mars",
    "artemis",
    "ground station",
    "space domain awareness",
    "missile warning",
    "overhead persistent infrared",
    "gps",
    "position, navigation",
    "pnt",
    "rocket",
    "propulsion",
    "payload",
    "constellation",
    "leo",
    "geo",
    "reentry",
    "hypersonic",
    "iss",
    "space station",
    "telemetry",
    "remote sensing",
    "geoint",
    "reconnaissance",
]

# Substrings matched (case-insensitive) against SAM.gov fullParentPathName / department names.
TARGET_AGENCIES = {
    "USSF": ["space force", "space systems command", "space operations command", "space training and readiness"],
    "NASA": ["national aeronautics and space administration", "nasa"],
    "NRO": ["national reconnaissance office"],
    "SDA": ["space development agency"],
    "MDA": ["missile defense agency"],
    "GSA-AAS": ["federal acquisition service", "assisted acquisition", "fedsim"],
}

# For agency-scoped SAM queries, every notice from these is kept even without a space keyword.
ALWAYS_KEEP_AGENCIES = {"USSF", "NASA", "NRO", "SDA"}

# Space-relevant NAICS / PSC prefixes used to widen SAM.gov filtering.
SPACE_NAICS = ["336414", "336415", "336419", "517410", "541715", "927110"]
SPACE_PSC_PREFIXES = ["18", "AR", "V1"]  # 18xx space vehicles, AR* space R&D, V1* transport of space

USER_AGENT = "space-opps-scraper/0.1 (+https://github.com)"
