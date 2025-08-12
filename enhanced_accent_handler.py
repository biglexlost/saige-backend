#!/usr/bin/env python3
"""
Enhanced Southern Accent and Phonetic Processing Module for JAIMES
Specifically designed for North Carolina dialects and heavy Southern drawl
"""

import re
import logging
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NameExtractionResult:
    """Result of name extraction with confidence scoring"""

    name: str
    confidence: float
    method: str
    alternatives: List[str]


class SouthernAccentHandler:
    """Enhanced handler for Southern accents and dialects"""

    def __init__(self):
        # Enhanced phonetic mapping for Southern pronunciation
        self.phonetic_map = {
            "ALPHA": "A",
            "AY": "A",
            "AYE": "A",
            "EH": "A",
            "A": "A",
            "BRAVO": "B",
            "BEE": "B",
            "BE": "B",
            "B": "B",
            "CHARLIE": "C",
            "SEE": "C",
            "SEA": "C",
            "C": "C",
            "DELTA": "D",
            "DEE": "D",
            "D": "D",
            "ECHO": "E",
            "E": "E",
            "EE": "E",
            "FOXTROT": "F",
            "EF": "F",
            "EFF": "F",
            "F": "F",
            "GOLF": "G",
            "GEE": "G",
            "JEE": "G",
            "G": "G",
            "HOTEL": "H",
            "AITCH": "H",
            "AYCH": "H",
            "H": "H",
            "INDIA": "I",
            "EYE": "I",
            "I": "I",
            "JULIET": "J",
            "JAY": "J",
            "J": "J",
            "KILO": "K",
            "KAY": "K",
            "K": "K",
            "LIMA": "L",
            "EL": "L",
            "ELL": "L",
            "L": "L",
            "MIKE": "M",
            "EM": "M",
            "M": "M",
            "NOVEMBER": "N",
            "EN": "N",
            "N": "N",
            "OSCAR": "O",
            "OH": "O",
            "O": "O",
            "PAPA": "P",
            "PEE": "P",
            "P": "P",
            "QUEBEC": "Q",
            "CUE": "Q",
            "QUE": "Q",
            "Q": "Q",
            "ROMEO": "R",
            "AR": "R",
            "ARE": "R",
            "R": "R",
            "SIERRA": "S",
            "ES": "S",
            "ESS": "S",
            "S": "S",
            "TANGO": "T",
            "TEE": "T",
            "T": "T",
            "UNIFORM": "U",
            "YOU": "U",
            "U": "U",
            "VICTOR": "V",
            "VEE": "V",
            "V": "V",
            "WHISKEY": "W",
            "DOUBLE YOU": "W",
            "DOUBLEYOU": "W",
            "W": "W",
            "XRAY": "X",
            "EX": "X",
            "X": "X",
            "YANKEE": "Y",
            "WHY": "Y",
            "Y": "Y",
            "ZULU": "Z",
            "ZEE": "Z",
            "ZED": "Z",
            "Z": "Z",
        }

        # Southern dialect variations and common mispronunciations
        self.southern_variations = {
            "ALFUH": "A",
            "ALFAH": "A",
            "BRAVUH": "B",
            "CHAR-LEE": "C",
            "DEL-TUH": "D",
            "ECK-OH": "E",
            "FOKS-TROT": "F",
            "GAWLF": "G",
            "HOH-TEL": "H",
            "IN-DEE-UH": "I",
            "JOO-LEE-ET": "J",
            "KEE-LOH": "K",
            "LEE-MUH": "L",
            "MY-KEE": "M",
            "NO-VEM-BUH": "N",
            "AHS-KUH": "O",
            "PAH-PUH": "P",
            "KEH-BECK": "Q",
            "ROH-MEE-OH": "R",
            "SEE-AIR-UH": "S",
            "TAN-GOH": "T",
            "YOO-NEE-FORM": "U",
            "VIK-TUH": "V",
            "WHIS-KEE": "W",
            "EKS-RAY": "X",
            "YANG-KEE": "Y",
            "ZOO-LOO": "Z",
        }

        # Common Southern name patterns and variations
        self.southern_name_patterns = {
            "MARY": ["MARY", "MARIE", "MERRY"],
            "JOHN": ["JOHN", "JOHNNY", "JON"],
            "JAMES": ["JAMES", "JIMMY", "JIM"],
            "WILLIAM": ["WILLIAM", "BILLY", "BILL", "WILL"],
            "ROBERT": ["ROBERT", "BOBBY", "BOB"],
            "MICHAEL": ["MICHAEL", "MIKE"],
            "DAVID": ["DAVID", "DAVE"],
            "RICHARD": ["RICHARD", "RICK", "RICKY"],
            "THOMAS": ["THOMAS", "TOM", "TOMMY"],
            "CHARLES": ["CHARLES", "CHARLIE", "CHUCK"],
            "CHRISTOPHER": ["CHRISTOPHER", "CHRIS"],
            "DANIEL": ["DANIEL", "DAN", "DANNY"],
            "MATTHEW": ["MATTHEW", "MATT"],
            "ANTHONY": ["ANTHONY", "TONY"],
            "ELIZABETH": ["ELIZABETH", "LIZ", "BETH", "BETTY"],
            "JENNIFER": ["JENNIFER", "JEN", "JENNY"],
            "SUSAN": ["SUSAN", "SUE", "SUSIE"],
            "MARGARET": ["MARGARET", "MAGGIE", "PEGGY"],
            "SARAH": ["SARAH", "SARA"],
            "KIMBERLY": ["KIMBERLY", "KIM"],
            "DEBORAH": ["DEBORAH", "DEBBIE", "DEB"],
            "JESSICA": ["JESSICA", "JESSIE"],
            "CYNTHIA": ["CYNTHIA", "CINDY"],
            "ANGELA": ["ANGELA", "ANGIE"],
            "MELISSA": ["MELISSA", "MISSY"],
            "REBECCA": ["REBECCA", "BECKY"],
        }

        # Southern expressions and colloquialisms
        self.southern_expressions = {
            "BLESS YOUR HEART": "polite_concern",
            "WELL I DECLARE": "surprise",
            "FIXIN TO": "about_to",
            "MIGHT COULD": "maybe_can",
            "RECKON": "think",
            "YALL": "you_all",
            "ALL YALL": "all_of_you",
            "OVER YONDER": "over_there",
            "A SPELL": "a_while",
        }

        # Common Southern mispronunciations and variations
        self.pronunciation_variations = {
            "PIN": "PEN",
            "TEN": "TIN",
            "AGAIN": "AGIN",
            "ABOUT": "ABOWT",
            "HOUSE": "HOWSE",
            "OUT": "OWT",
            "TIME": "TAHM",
            "NICE": "NAHS",
            "RIDE": "RAHD",
            "FIRE": "FAHR",
            "TIRE": "TAHR",
            "WIRE": "WAHR",
        }

    def normalize_speech(self, text: str) -> str:
        """Normalize common Southern forms to standard English for NLP.
        Safe, conservative replacements only.
        """
        if not text:
            return text
        original = text
        normalized = text

        # Apostrophe variants to plain ASCII for consistency
        normalized = normalized.replace("’", "'")

        # Common colloquialisms
        replacements = {
            "y'all": "you all",
            "yall": "you all",
            "fixin to": "about to",
            "fixing to": "about to",
            "gonna": "going to",
            "gotta": "have to",
            "kinda": "kind of",
            "sorta": "sort of",
            "lemme": "let me",
            "gimme": "give me",
            "ain't": "is not",
        }

        # Case-insensitive whole-word-ish replacements
        for k, v in replacements.items():
            normalized = re.sub(rf"\b{re.escape(k)}\b", v, normalized, flags=re.IGNORECASE)

        # Phonetic endings: "ing" pronounced as "in'"
        normalized = re.sub(r"\b(\w+?)in'\b", r"\1ing", normalized)

        # Trim repeated whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized if normalized else original

    def extract_spelled_name(self, text: str) -> Optional[str]:
        """Extract phonetically spelled names with enhanced Southern dialect support"""
        text = text.upper().strip()

        dash_pattern = re.findall(r"[A-Z](?:\s*[-\s]\s*[A-Z])+", text)
        if dash_pattern:
            name = re.sub(r"[-\s]", "", dash_pattern[0])
            if len(name) >= 2:
                return name.title()

        combined_map = {**self.phonetic_map, **self.southern_variations}
        words = text.split()

        if all(w in combined_map for w in words):
            return "".join(combined_map[w] for w in words).title()

        if len(words) >= 2:
            letters = []
            confidence = 0
            for word in words:
                if word in combined_map:
                    letters.append(combined_map[word])
                    confidence += 1
                elif len(word) == 1 and word.isalpha():
                    letters.append(word)
                    confidence += 0.5
                else:
                    best_match = self._fuzzy_phonetic_match(word)
                    if best_match:
                        letters.append(best_match)
                        confidence += 0.3

            if confidence >= len(words) * 0.6:
                result = "".join(letters).title()
                if len(result) >= 2:
                    return result

        return None

    def _fuzzy_phonetic_match(self, word: str) -> Optional[str]:
        """Fuzzy matching for Southern pronunciation variations"""
        word = word.upper()

        if word in self.pronunciation_variations:
            corrected = self.pronunciation_variations[word]
            if corrected in self.phonetic_map:
                return self.phonetic_map[corrected]

        substitutions = [
            ("AH", "A"),
            ("UH", "A"),
            ("EH", "A"),
            ("OH", "O"),
            ("AW", "O"),
            ("EE", "E"),
            ("IH", "I"),
            ("OO", "U"),
            ("UH", "U"),
        ]
        for old, new in substitutions:
            if old in word:
                modified = word.replace(old, new)
                if modified in self.phonetic_map:
                    return self.phonetic_map[modified]

        if word.endswith(("N", "G")) and word[:-1] in self.phonetic_map:
            return self.phonetic_map[word[:-1]]

        return None

    def extract_name_with_context(
        self, messages: List[Dict], current_stage: str
    ) -> NameExtractionResult:
        """Enhanced name extraction with context awareness and confidence scoring"""
        alternatives = []
        best_result = None
        highest_confidence = 0

        for msg in reversed(messages[-3:]):
            if msg["role"] == "user":
                content = msg["content"].strip()

                spelled = self.extract_spelled_name(content)
                if spelled:
                    confidence = 0.95 if len(spelled) >= 3 else 0.9
                    result = NameExtractionResult(
                        name=spelled,
                        confidence=confidence,
                        method="phonetic_spelling",
                        alternatives=[],
                    )
                    if confidence > highest_confidence:
                        highest_confidence = confidence
                        best_result = result

                patterns = [
                    r"(?:my name is|it's|i'm|this is|call me)\s+([a-zA-Z]+)",
                    r"^([a-zA-Z]+)$",
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        name = match.group(1).title()
                        if len(name) >= 2 and name.isalpha():
                            confidence = (
                                0.85
                                if name.upper() in self.southern_name_patterns
                                else 0.7
                            )
                            name_alternatives = self.southern_name_patterns.get(
                                name.upper(), []
                            )
                            result = NameExtractionResult(
                                name=name,
                                confidence=confidence,
                                method="pattern_match",
                                alternatives=name_alternatives,
                            )
                            if confidence > highest_confidence:
                                highest_confidence = confidence
                                best_result = result
                            alternatives.append(result)

        if best_result:
            best_result.alternatives = [
                alt.name for alt in alternatives if alt.name != best_result.name
            ]
            return best_result

        return NameExtractionResult(
            name="", confidence=0.0, method="none", alternatives=[]
        )

    def detect_southern_expressions(self, text: str) -> List[Tuple[str, str]]:
        """Detect Southern expressions and colloquialisms"""
        text = text.upper()
        detected = []
        for expression, meaning in self.southern_expressions.items():
            if expression in text:
                detected.append((expression, meaning))
        return detected

    def enhance_voice_response_for_accent(self, text: str) -> str:
        """Enhance voice response to be more natural for Southern listeners"""
        text = text.replace(". ", ". <break time='700ms'/> ")
        text = text.replace("? ", "? <break time='600ms'/> ")

        emphasis_words = ["y'all", "please", "thank", "appreciate", "help", "service"]
        for word in emphasis_words:
            pattern = r"\b" + re.escape(word) + r"\b"
            replacement = f'<emphasis level="moderate">{word}</emphasis>'
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        text = f"<prosody rate='0.9'>{text}</prosody>"
        return f"<speak>{text}</speak>"

    def get_clarification_response(self, attempt_count: int, context: str = "") -> str:
        """Get appropriate clarification response based on attempt count and context"""
        southern_clarifications = [
            "I'm sorry, I didn't quite catch that. Could you say that again for me?",
            "Pardon me, I'm having a little trouble hearing you clearly. Could you repeat that?",
            "I apologize, but I didn't get that. Would you mind saying it one more time?",
            "I'm having some difficulty understanding. Let me get someone from our team to help you better.",
        ]
        return southern_clarifications[
            min(attempt_count, len(southern_clarifications) - 1)
        ]


# Example usage and testing
if __name__ == "__main__":
    handler = SouthernAccentHandler()

    test_cases = [
        "My name is spelled J-A-M-E-S",
        "It's spelled M-A-R-Y",
        "Call me Billy Bob",
        "I'm fixin to bring my truck in",
        "Y'all got any appointments today?",
        "Bless your heart, I reckon my car's broke",
        "ALFUH BRAVUH CHAR-LEE DEL-TUH",
        "A-N-N-A with dashes",
        "My name is Bobby Joe",
        "It's spelled out as DEE EE BEE BEE EYE EE",
    ]

    print("Testing Southern Accent Handler:")
    print("=" * 50)

    for test in test_cases:
        print(f"\nInput: '{test}'")

        spelled = handler.extract_spelled_name(test)
        if spelled:
            print(f"Spelled name: {spelled}")

        expressions = handler.detect_southern_expressions(test)
        if expressions:
            print(f"Southern expressions: {expressions}")

        enhanced = handler.enhance_voice_response_for_accent(test)
        print(f"Enhanced voice: {enhanced}")
        print("-" * 30)
