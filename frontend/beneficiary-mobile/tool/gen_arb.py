"""Generate lib/l10n/app_{en,hi,kn}.arb from tool/strings.py.

Fails loudly if a language is missing a key, has an extra key, or uses different {placeholders} than English,
so a translation can never silently drift out of sync.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from strings import EN, HI, KN  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "lib" / "l10n"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def check(lang: str, table: dict) -> None:
    missing, extra = set(EN) - set(table), set(table) - set(EN)
    if missing or extra:
        sys.exit(f"{lang}: missing {sorted(missing)} extra {sorted(extra)}")
    for key, text in table.items():
        if set(PLACEHOLDER.findall(text)) != set(PLACEHOLDER.findall(EN[key])):
            sys.exit(f"{lang}.{key}: placeholders {PLACEHOLDER.findall(text)} != English {PLACEHOLDER.findall(EN[key])}")
        if not text.strip():
            sys.exit(f"{lang}.{key}: empty")


def emit(locale: str, table: dict, with_meta: bool) -> None:
    arb: dict = {"@@locale": locale}
    for key, text in table.items():
        arb[key] = text
        names = PLACEHOLDER.findall(EN[key])
        if with_meta and names:  # placeholder metadata lives in the template (English) file
            arb["@" + key] = {"placeholders": {n: {"type": "String"} for n in names}}
    (OUT / f"app_{locale}.arb").write_text(json.dumps(arb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for lang, table in (("hi", HI), ("kn", KN)):
        check(lang, table)
    emit("en", EN, True)
    emit("hi", HI, False)
    emit("kn", KN, False)
    print(f"generated {len(EN)} strings x 3 languages")
