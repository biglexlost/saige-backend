"""
Minimal med-spa service catalog used to guide intent and intake.
"""

from typing import Dict, List, Optional


# medspa_service_catalog.py

# Core service categories aligned with your CRM
MEDSPA_SERVICES = {
    "consultation": {
        "description": "Initial consultation and skin assessment",
        "duration_minutes": 30,
        "price_range": "$0 - $100",
        "crm_tags": ["consult-booked", "lead-cold"],
        "intake": [
            "What are your main skin concerns?",
            "Have you had treatments before?",
            "What's your skincare routine like?",
            "Any allergies or medical conditions?",
            "What results are you hoping to achieve?"
        ]
    },
    "facial": {
        "description": "Customized facial treatments",
        "duration_minutes": 60,
        "price_range": "$100 - $250",
        "crm_tags": ["prep-sent", "aftercare-sent"],
        "intake": [
            "Which facial type interests you? (Hydrating, Anti-aging, Acne, etc.)",
            "Have you had a facial with us before?",
            "Any specific skin concerns to address?",
            "Are you looking for relaxation or results-focused treatment?"
        ]
    },
    "botox": {
        "description": "Botox injections for wrinkle reduction",
        "duration_minutes": 30,
        "price_range": "$300 - $800",
        "crm_tags": ["prep-sent", "aftercare-sent", "7day-followup-sent"],
        "intake": [
            "Have you had Botox before?",
            "Which areas are you interested in treating?",
            "Any allergies or medical conditions?",
            "What's your timeline for results?"
        ]
    },
    "filler": {
        "description": "Dermal fillers for volume restoration",
        "duration_minutes": 45,
        "price_range": "$500 - $1200",
        "crm_tags": ["prep-sent", "aftercare-sent", "7day-followup-sent"],
        "intake": [
            "Have you had fillers before?",
            "Which areas are you interested in treating?",
            "Any allergies or medical conditions?",
            "What's your budget range?"
        ]
    },
    "laser": {
        "description": "Laser treatments for skin rejuvenation and hair removal",
        "duration_minutes": 60,
        "price_range": "$100 - $500 per session",
        "crm_tags": ["prep-sent", "aftercare-sent", "7day-followup-sent"],
        "intake": [
            "Which area of your body are you interested in treating?",
            "What is your skin type?",
            "Have you had laser treatments before?",
            "Are you prepared for multiple sessions?"
        ]
    },
    "massage": {
        "description": "Therapeutic massage therapy",
        "duration_minutes": 90,
        "price_range": "$150 - $300",
        "crm_tags": ["prep-sent", "aftercare-sent"],
        "intake": [
            "Are you looking for deep tissue, Swedish, or hot stone massage?",
            "Do you have any areas of tension or pain we should focus on?",
            "Do you have any medical conditions or allergies we should be aware of?",
            "What's your preferred pressure level?"
        ]
    }
}

# CRM Tag Categories for Automation Triggers
CRM_TAG_CATEGORIES = {
    "lead_management": [
        "lead-cold", "lead-abandoned-consult", "consult-booked"
    ],
    "treatment_flow": [
        "prep-sent", "aftercare-sent", "7day-followup-sent", "upsell-sent"
    ],
    "booking_status": [
        "booking-confirmed", "confirmed-by-sms", "slot-claimed", "confirmation-issue"
    ],
    "membership": [
        "membership-active", "membership-expiring", "membership-cancelled"
    ],
    "rfm_segmentation": [
        "rfm-reactivation", "rfm-reactivation-sent", "rfm-reactivation-complete",
        "rfm-champion", "rfm-promoter", "rfm-detractor"
    ],
    "engagement": [
        "review-requested", "review-posted", "referral-ask-sent", "referral-accepted",
        "ugc-requested", "ugc-received", "vip-invite-sent"
    ],
    "retention": [
        "long-nurture-active", "giftcard-expiring"
    ]
}

# Automation Phases (matching your CRM structure)
AUTOMATION_PHASES = {
    "phase_1": {
        "name": "New Lead Nurture (Fast 5)",
        "triggers": ["consult-booked", "lead-cold"],
        "tags": ["lead-cold"]
    },
    "phase_2": {
        "name": "Treatment Flow & Recovery",
        "triggers": ["booking-confirmed", "lead-abandoned-consult"],
        "tags": ["prep-sent", "aftercare-sent", "upsell-sent"]
    },
    "phase_3": {
        "name": "Lead Nurture & Reactivation",
        "triggers": ["rfm-reactivation", "membership-expiring"],
        "tags": ["rfm-reactivation-sent", "long-nurture-active"]
    },
    "phase_4": {
        "name": "Reviews, Referrals & Advocacy",
        "triggers": ["visit-attended", "membership-active"],
        "tags": ["review-requested", "referral-ask-sent", "vip-invite-sent"]
    }
}

def match_service(user_input: str) -> Optional[str]:
    """
    Matches user input to a known med-spa service.
    Returns the service key if a match is found, otherwise None.
    """
    normalized_input = user_input.lower()
    
    # Direct service name matching
    for service_name, details in MEDSPA_SERVICES.items():
        if service_name in normalized_input:
            return service_name
    
    # Alias matching for common terms
    service_aliases = {
        "consult": "consultation",
        "skin": "consultation",
        "assessment": "consultation",
        "hydrafacial": "facial",
        "anti-aging": "facial",
        "acne treatment": "facial",
        "wrinkle": "botox",
        "injection": "botox",
        "volume": "filler",
        "plump": "filler",
        "hair removal": "laser",
        "skin tightening": "laser",
        "therapeutic": "massage",
        "relaxation": "massage"
    }
    
    for alias, service in service_aliases.items():
        if alias in normalized_input:
            return service
    
    return None

def get_crm_tags_for_service(service: str) -> List[str]:
    """Get CRM tags that should be applied for a specific service."""
    if service in MEDSPA_SERVICES:
        return MEDSPA_SERVICES[service].get("crm_tags", [])
    return []

def get_automation_phase_for_tags(tags: List[str]) -> Optional[str]:
    """Determine which automation phase should be triggered based on CRM tags."""
    for phase, config in AUTOMATION_PHASES.items():
        if any(tag in config["triggers"] for tag in tags):
            return phase
    return None

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


