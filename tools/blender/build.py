"""Regenerate Turbo Turma models from code.

    bpython tools/blender/build.py karts            # all kart parts
    bpython tools/blender/build.py karts --preview  # + review renders in tools/blender/out
    bpython tools/blender/build.py guara track props
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MODELS = os.path.join(ROOT, "assets", "models")
OUT = os.path.join(HERE, "out")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    groups = [a for a in argv if not a.startswith("-")]
    preview = "--preview" in argv
    os.makedirs(OUT, exist_ok=True)
    for g in groups:
        print("== building", g)
        if g == "karts":
            import kart_parts
            kart_parts.build(MODELS, os.path.join(OUT, "kart") if preview else None)
        elif g == "kart_variants":
            import kart_parts
            kart_parts.review_variants(os.path.join(OUT, "kart"))
        elif g == "guara_review":
            import guara
            guara.review_model(os.path.join(OUT, "guara"))
        elif g == "kart_review":
            import kart_parts
            kart_parts.review(MODELS, os.path.join(OUT, "kart"))
        else:
            mod = __import__(g)
            mod.build(MODELS, os.path.join(OUT, g) if preview else None)


if __name__ == "__main__":
    main()
