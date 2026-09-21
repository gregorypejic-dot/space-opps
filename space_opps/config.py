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

# When "space" is the only keyword hit, these mark it as real estate (office/hangar/warehouse
# leasing) rather than outer space, and the item is dropped.
REAL_ESTATE_SPACE = [
    r"\bleas(e|es|ed|ing)\b",
    r"\brlp\b",
    r"\b(office|hangar|warehouse|storage|retail|clinic|laboratory|lab|parking|administrative|"
    r"related|swing|expansion|contiguous|rentable|usable|aboa)\s+(and\s+related\s+)?space\b",
    r"\bspace\s+(in|near|for lease|requirements?|required|to lease)\b",
    r"\b(confined|motor pool|floor|shelf|green|open)\s+space\b",
    r"\bseek(s|ing)?\s+(to\s+lease\s+)?(the\s+following\s+)?(office\s+)?space\b",
    r"\b(sq\.?\s*ft|square\s+f(ee|oo)t|sf)\b",
]

# Substrings matched (case-insensitive) against SAM.gov fullParentPathName / department names.
TARGET_AGENCIES = {
    "USSF": ["space force", "space systems command", "space operations command", "space training and readiness"],
    "NASA": ["national aeronautics and space administration", "nasa"],
    "NRO": ["national reconnaissance office"],
    "SDA": ["space development agency"],
    "MDA": ["missile defense agency"],
    "DOC-OSC": ["office of space commerce", "space commerce"],
    "NOAA": ["national oceanic and atmospheric administration", "noaa", "nesdis"],
    "GSA-AAS": ["federal acquisition service", "assisted acquisition", "fedsim"],
}

# For agency-scoped SAM queries, every notice from these is kept even without a space keyword.
ALWAYS_KEEP_AGENCIES = {"USSF", "NASA", "NRO", "SDA", "DOC-OSC"}

# Space-relevant NAICS / PSC prefixes used to widen SAM.gov filtering.
SPACE_NAICS = ["336414", "336415", "336419", "517410", "541715", "927110"]
SPACE_PSC_PREFIXES = ["18", "AR", "V1"]  # 18xx space vehicles, AR* space R&D, V1* transport of space

USER_AGENT = "space-opps-scraper/0.1 (+https://github.com)"
