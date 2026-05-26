# Copyright (c) 2026, Klisia and contributors
# For license information, please see license.txt

"""Book name → OSIS code map for the api.bible reference parser.

api.bible's /passages endpoint requires OSIS-style book codes (GEN, JHN, 1JN…).
Profs type natural names (Jn, John, João, Joao, Sl, Salmos, Ps, Psalm…). This
module owns the alias table for the 66-book Protestant canon in English and
Brazilian Portuguese.

Disambiguation notes:
- Bare "jo" / "jó" is NOT in the map. After diacritic-stripping both normalize
  to "jo", which is ambiguous (PT: Jó = Job vs Jo = João = John). Use one of:
  "job" or "jb" for Job; "jn" / "joh" / "joao" / "joão" / "john" for John.
- "hb" maps to HEB (Hebreus is the common modern usage); for Habacuque use "hc".
- Number prefixes use Arabic digits only (1sa, 2co), not Roman (I Sam). The
  "I "/"II " literal prefixes ARE supported (case-insensitive) where I included
  them.
"""

import re
import unicodedata


def normalize(s: str) -> str:
    """Lowercase, strip diacritics, strip whitespace and dots.

    "João" → "joao", "1 Cor." → "1cor", "I JOÃO" → "ijoao".
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    return re.sub(r"[\s.]+", "", s)


# (OSIS code, [aliases — written in their natural form; normalization happens at build time])
# Aliases include: full EN name, common EN abbreviations, full PT name, common PT abbreviations.
_BOOKS = [
    # === Old Testament ===
    ("GEN", ["Genesis", "Gen", "Gn", "Ge", "Gênesis"]),
    ("EXO", ["Exodus", "Exo", "Exod", "Ex", "Êxodo", "Exodo"]),
    ("LEV", ["Leviticus", "Lev", "Lv", "Levítico", "Levitico"]),
    ("NUM", ["Numbers", "Num", "Nm", "Nu", "Números", "Numeros"]),
    ("DEU", ["Deuteronomy", "Deut", "Deu", "Dt", "Deuteronômio", "Deuteronomio"]),
    ("JOS", ["Joshua", "Josh", "Jos", "Js", "Josué", "Josue"]),
    ("JDG", ["Judges", "Judg", "Jdg", "Jg", "Juízes", "Juizes", "Jz"]),
    ("RUT", ["Ruth", "Rut", "Ru", "Rute", "Rt"]),
    ("1SA", ["1 Samuel", "1Samuel", "1 Sam", "1Sam", "1Sa", "1Sm", "I Samuel"]),
    ("2SA", ["2 Samuel", "2Samuel", "2 Sam", "2Sam", "2Sa", "2Sm", "II Samuel"]),
    ("1KI", ["1 Kings", "1Kings", "1 Kgs", "1Kgs", "1Ki", "1Reis", "1 Reis", "1Rs"]),
    ("2KI", ["2 Kings", "2Kings", "2 Kgs", "2Kgs", "2Ki", "2Reis", "2 Reis", "2Rs"]),
    (
        "1CH",
        [
            "1 Chronicles",
            "1Chronicles",
            "1 Chron",
            "1Chr",
            "1Ch",
            "1 Crônicas",
            "1Cronicas",
            "1Cr",
        ],
    ),
    (
        "2CH",
        [
            "2 Chronicles",
            "2Chronicles",
            "2 Chron",
            "2Chr",
            "2Ch",
            "2 Crônicas",
            "2Cronicas",
            "2Cr",
        ],
    ),
    ("EZR", ["Ezra", "Ezr", "Esdras", "Ed"]),
    ("NEH", ["Nehemiah", "Neh", "Ne", "Neemias"]),
    ("EST", ["Esther", "Est", "Et", "Ester"]),
    (
        "JOB",
        ["Job", "Jb"],
    ),  # "Jó" excluded — collides with "Jo" (João) after diacritic strip
    ("PSA", ["Psalms", "Psalm", "Pss", "Ps", "Psa", "Pslm", "Salmos", "Salmo", "Sl"]),
    ("PRO", ["Proverbs", "Prov", "Pro", "Pr", "Provérbios", "Proverbios", "Pv"]),
    ("ECC", ["Ecclesiastes", "Eccl", "Ecc", "Ec", "Eclesiastes"]),
    (
        "SNG",
        [
            "Song of Solomon",
            "Song of Songs",
            "Song",
            "SoS",
            "Sng",
            "Cantares",
            "Cantico",
            "Cânticos",
            "Canticos",
            "Ct",
        ],
    ),
    ("ISA", ["Isaiah", "Isa", "Is", "Isaías", "Isaias"]),
    ("JER", ["Jeremiah", "Jer", "Jr", "Jeremias"]),
    ("LAM", ["Lamentations", "Lam", "Lm", "Lamentações", "Lamentacoes"]),
    ("EZK", ["Ezekiel", "Ezek", "Ezk", "Eze", "Ez", "Ezequiel"]),
    ("DAN", ["Daniel", "Dan", "Dn", "Da"]),
    ("HOS", ["Hosea", "Hos", "Ho", "Os", "Oséias", "Oseias"]),
    ("JOL", ["Joel", "Jl"]),
    ("AMO", ["Amos", "Am", "Amó", "Amós"]),
    ("OBA", ["Obadiah", "Obad", "Oba", "Ob", "Obadias"]),
    ("JON", ["Jonah", "Jon", "Jnh", "Jonas"]),
    ("MIC", ["Micah", "Mic", "Mi", "Miquéias", "Miqueias", "Mq"]),
    ("NAM", ["Nahum", "Nah", "Na", "Naum"]),
    ("HAB", ["Habakkuk", "Hab", "Hc", "Habacuque"]),  # "Hb" reserved for Hebreus (HEB)
    ("ZEP", ["Zephaniah", "Zeph", "Zep", "Zph", "Sofonias", "Sf"]),
    ("HAG", ["Haggai", "Hag", "Hg", "Ag", "Ageu"]),
    ("ZEC", ["Zechariah", "Zech", "Zec", "Zac", "Zc", "Zacarias"]),
    ("MAL", ["Malachi", "Mal", "Ml", "Malaquias"]),
    # === New Testament ===
    ("MAT", ["Matthew", "Matt", "Mat", "Mt", "Mateus"]),
    ("MRK", ["Mark", "Mrk", "Mk", "Mc", "Marcos"]),
    ("LUK", ["Luke", "Luk", "Lk", "Lu", "Lc", "Lucas"]),
    (
        "JHN",
        ["John", "Jhn", "Jn", "João", "Joao"],
    ),  # "Jo" excluded — see disambiguation note
    ("ACT", ["Acts", "Act", "Ac", "At", "Atos"]),
    ("ROM", ["Romans", "Rom", "Ro", "Rm", "Romanos"]),
    (
        "1CO",
        [
            "1 Corinthians",
            "1Corinthians",
            "1 Cor",
            "1Cor",
            "1Co",
            "1 Coríntios",
            "1Corintios",
        ],
    ),
    (
        "2CO",
        [
            "2 Corinthians",
            "2Corinthians",
            "2 Cor",
            "2Cor",
            "2Co",
            "2 Coríntios",
            "2Corintios",
        ],
    ),
    ("GAL", ["Galatians", "Gal", "Ga", "Gl", "Gálatas", "Galatas"]),
    ("EPH", ["Ephesians", "Eph", "Ep", "Ef", "Efésios", "Efesios"]),
    ("PHP", ["Philippians", "Phil", "Php", "Phlp", "Fp", "Filipenses"]),
    ("COL", ["Colossians", "Col", "Cl", "Colossenses"]),
    (
        "1TH",
        [
            "1 Thessalonians",
            "1Thessalonians",
            "1 Thess",
            "1Thess",
            "1Th",
            "1 Tessalonicenses",
            "1Tessalonicenses",
            "1Ts",
        ],
    ),
    (
        "2TH",
        [
            "2 Thessalonians",
            "2Thessalonians",
            "2 Thess",
            "2Thess",
            "2Th",
            "2 Tessalonicenses",
            "2Tessalonicenses",
            "2Ts",
        ],
    ),
    (
        "1TI",
        [
            "1 Timothy",
            "1Timothy",
            "1 Tim",
            "1Tim",
            "1Ti",
            "1Tm",
            "1 Timóteo",
            "1Timoteo",
        ],
    ),
    (
        "2TI",
        [
            "2 Timothy",
            "2Timothy",
            "2 Tim",
            "2Tim",
            "2Ti",
            "2Tm",
            "2 Timóteo",
            "2Timoteo",
        ],
    ),
    ("TIT", ["Titus", "Tit", "Ti", "Tt", "Tito"]),
    ("PHM", ["Philemon", "Philem", "Phm", "Pm", "Fm", "Filemom", "Filemon"]),
    ("HEB", ["Hebrews", "Heb", "He", "Hb", "Hebreus"]),
    ("JAS", ["James", "Jas", "Jm", "Tg", "Tiago"]),
    ("1PE", ["1 Peter", "1Peter", "1 Pet", "1Pet", "1Pe", "1Pt", "1 Pedro", "1Pedro"]),
    ("2PE", ["2 Peter", "2Peter", "2 Pet", "2Pet", "2Pe", "2Pt", "2 Pedro", "2Pedro"]),
    ("1JN", ["1 John", "1John", "1 Jn", "1Jn", "1Jhn", "1 João", "1Joao", "1Jo"]),
    ("2JN", ["2 John", "2John", "2 Jn", "2Jn", "2Jhn", "2 João", "2Joao", "2Jo"]),
    ("3JN", ["3 John", "3John", "3 Jn", "3Jn", "3Jhn", "3 João", "3Joao", "3Jo"]),
    ("JUD", ["Jude", "Jud", "Jd", "Judas"]),
    ("REV", ["Revelation", "Rev", "Re", "Ap", "Apocalipse"]),
]


# Pre-built lookup: normalized alias → OSIS code.
BOOK_ALIASES: dict[str, str] = {}
for _osis, _aliases in _BOOKS:
    for _alias in _aliases:
        _key = normalize(_alias)
        # First write wins for collisions (order in _BOOKS matters).
        # The "jo" alias under JHN intentionally wins over any Job aliasing —
        # see the disambiguation note in the module docstring.
        BOOK_ALIASES.setdefault(_key, _osis)
