"""A shortlist of Kokoro voices, with grades, for picking a narrator.

`voices.py` is an ElevenLabs client: it lists, auditions and saves ElevenLabs voices over
their API. Nothing in the pipeline catalogues the *local* Kokoro voices, even though those
are the default, so choosing one means knowing a name like `af_heart` by heart. This is that
missing list: the voices worth considering, not all of them.

The grades are Kokoro's own, published with the model (A is best, C is usable). A Kokoro
name encodes its language and gender: the first letter is the language (`a` American
English, `b` British English, `e` Spanish), the second the gender, then the name — which is
also how `tts.py` decides, with no flag, that a name means Kokoro rather than ElevenLabs or
macOS `say`.

Hear them before choosing: `voice_lab.py` renders every voice below, in English and in
Spanish, onto a local page with a play button each.

    python kokoro_catalog.py           # the shortlist
    python kokoro_catalog.py --all     # with the sample text each one reads in the lab
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

ENGLISH, SPANISH = "en", "es"


@dataclass(frozen=True)
class Voice:
    name: str
    language: str  # ENGLISH or SPANISH: which sample line it reads in the lab
    accent: str
    gender: str
    grade: str  # Kokoro's own grade, or "-" where it publishes none
    note: str


# Ordered best-first within each language: the lab lists them in this order.
VOICES = [
    Voice("af_heart", ENGLISH, "American", "female", "A",
          "the default; warm and even, the safest pick for a product demo"),
    Voice("af_bella", ENGLISH, "American", "female", "A-",
          "brighter and a little faster than af_heart"),
    Voice("af_nicole", ENGLISH, "American", "female", "B-",
          "softer, close-mic; quiet next to the others"),
    Voice("bf_emma", ENGLISH, "British", "female", "B-",
          "British; the one to pick for a UK audience"),
    Voice("am_puck", ENGLISH, "American", "male", "C+",
          "the most natural of the male voices"),
    Voice("am_michael", ENGLISH, "American", "male", "C+", "flatter, steady"),
    Voice("am_fenrir", ENGLISH, "American", "male", "C+", "deeper, slower"),
    Voice("ef_dora", SPANISH, "Spanish", "female", "-",
          "Spanish; Kokoro publishes no grade for these, so audition before committing"),
    Voice("em_alex", SPANISH, "Spanish", "male", "-", "Spanish"),
    Voice("em_santa", SPANISH, "Spanish", "male", "-", "Spanish; older, slower"),
]
BY_NAME = {v.name: v for v in VOICES}
DEFAULT = "af_heart"

# What each voice reads in the lab: ordinary product-demo copy, so the audition sounds like
# the job. The Spanish line is not a translation of the English one; both are natural copy.
SAMPLES = {
    ENGLISH: ("Let's see how it works. Open the app, choose a project, and tap the plus "
              "button to add your first task. Need to make a change? Just tap any item to "
              "edit it. There you go, everything is saved and ready to share!"),
    SPANISH: ("Veamos cómo funciona. Abre la aplicación, elige un proyecto y toca el botón "
              "con el signo más para agregar tu primera tarea. ¿Necesitas hacer un cambio? "
              "Solo toca cualquier elemento para editarlo. ¡Listo! Todo está guardado y "
              "preparado para compartir."),
}


def of(language: str | None = None) -> list[Voice]:
    return [v for v in VOICES if language is None or v.language == language]


def main() -> None:
    parser = argparse.ArgumentParser(description="The Kokoro voices worth considering.")
    parser.add_argument("--language", choices=(ENGLISH, SPANISH), help="only this language")
    parser.add_argument("--all", action="store_true", help="also print the lab's sample text")
    args = parser.parse_args()
    print(f"{'voice':<12} {'grade':<6} {'accent':<10} {'gender':<7} note")
    for voice in of(args.language):
        mark = "  (default)" if voice.name == DEFAULT else ""
        print(f"{voice.name:<12} {voice.grade:<6} {voice.accent:<10} {voice.gender:<7} "
              f"{voice.note}{mark}")
    print("\nHear them: python voice_lab.py --serve")
    if args.all:
        for language, text in SAMPLES.items():
            print(f"\n{language}: {text}")


if __name__ == "__main__":
    main()
