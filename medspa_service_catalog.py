from dataclasses import dataclass
from typing import List, Optional
import json
import os
from config import config


@dataclass
class Service:
    slug: str
    name: str
    category: str
    synonyms: List[str]


DEFAULT_SERVICES: List[Service] = [
    Service("botox", "Botox/Dysport", "Injectables", ["botox", "dysport", "wrinkle", "forehead"]),
    Service("filler", "Dermal Filler", "Injectables", ["filler", "lip filler", "cheek filler"]),
    Service("laser_hair", "Laser Hair Removal", "Laser", ["laser hair", "hair removal"]),
    Service("ipl", "IPL Photofacial", "Laser/Light", ["ipl", "photofacial"]),
    Service("rf_micro", "RF Microneedling", "Skin Rejuvenation", ["rf microneedling", "rf micro"]),
    Service("micro", "Microneedling", "Skin Rejuvenation", ["microneedling", "collagen"]),
    Service("facial", "Custom Facial", "Facials", ["facial", "deep clean", "hydration"]),
    Service("chemical_peel", "Chemical Peel", "Skin Rejuvenation", ["peel", "chemical peel"]),
    Service("dermaplaning", "Dermaplaning", "Facials", ["dermaplaning"]),
    Service("consult", "Consultation", "Consultation", ["consult", "free consult", "assessment"]),
    Service("lhr_pkg", "Laser Hair Package", "Packages", ["lhr package", "laser package"]),
    Service("membership", "Membership", "Memberships", ["membership", "monthly"]),
]


def load_catalog(path: Optional[str] = None) -> List[Service]:
    file_path = path or config.service_catalog_path
    if file_path and os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
        return [Service(**item) for item in data]
    return DEFAULT_SERVICES


