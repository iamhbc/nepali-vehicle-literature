from app.nlp.language import detect_language
from app.nlp.normalize import match_key, normalize_text, tokenize
from app.nlp.transliterate import transliterate


def test_normalize_keeps_text_but_cleans_noise():
    assert normalize_text("  माया\\-  प्रेम  ") == "माया- प्रेम"
    assert normalize_text("‘माया’") == "'माया'"


def test_match_key_folds_common_spelling_variants():
    assert match_key("जिन्दगी होइन") == match_key("जिन्दगि होइन")
    assert match_key("पीडा") == match_key("पिडा")
    assert match_key("कहाँ") == match_key("कहां")
    # Vowel signs survive (regression: \\w does not cover Devanagari matras).
    assert "ा" in match_key("माया")


def test_tokenize_splits_on_danda_and_punctuation():
    assert tokenize("भाडा लिऊँ भने; आफू नाङ्गो।") == ["भाडा", "लिऊँ", "भने", "आफू", "नाङ्गो"]


def test_transliteration_applies_nepali_schwa_rules():
    assert transliterate("माया") == "Māyā"
    assert transliterate("इष्ट") == "Iṣṭa"            # final cluster keeps 'a'
    assert transliterate("रहेछ") == "Rahecha"          # छ verb ending keeps 'a'
    assert transliterate("छैन") == "Chaina"            # negative keeps 'a'
    assert transliterate("मन") == "Man"                # final schwa deleted
    assert transliterate("चुपचाप") == "Cupcāp"         # medial schwa deleted
    assert transliterate("प्रभु") == "Prabhu"
    assert transliterate("‘प्यार’ भन्छे") == "‘Pyār’ bhanche"  # curly quotes are punctuation


def test_language_detection():
    assert detect_language("माया भनेको सम्झना रहेछ").language == "ne"
    assert detect_language("timi lai maya garchu").language == "ne-Latn"
    assert detect_language("I love my truck").language == "en"
    assert detect_language("तिमी मेरै GF भए पनि").language in ("ne", "mixed")
