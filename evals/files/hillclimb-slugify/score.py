"""Scorer for slugify. The cases below ARE the spec — run me to see your score.

Usage: python score.py
"""
import sys

CASES = [
    ("Hello World", "hello-world"),
    ("  leading and trailing  ", "leading-and-trailing"),
    ("multiple   spaces", "multiple-spaces"),
    ("Under_scores_too", "under-scores-too"),
    ("Café au lait", "cafe-au-lait"),
    ("naïve résumé", "naive-resume"),
    ("Don't stop", "dont-stop"),
    ("rock & roll", "rock-and-roll"),
    ("C++ programming", "c-programming"),
    ("hello---world", "hello-world"),
    ("--already-slugged--", "already-slugged"),
    ("ALL CAPS", "all-caps"),
    ("tabs\tand\nnewlines", "tabs-and-newlines"),
    ("emoji \U0001F680 launch", "emoji-launch"),
    ("", ""),
    ("!!! ???", ""),
    ("Ünïcödé", "unicode"),
    ("São Paulo 2024!", "sao-paulo-2024"),
    (
        "the quick brown fox jumps over the lazy dog again",
        "the-quick-brown-fox-jumps-over-the-lazy",
    ),  # results longer than 40 chars are truncated, then trailing dashes stripped
    ("Ça va? Très bien!", "ca-va-tres-bien"),
]


def main():
    from solution import slugify

    passed = 0
    for i, (text, expected) in enumerate(CASES, 1):
        try:
            got = slugify(text)
        except Exception as e:
            got = f"<raised {type(e).__name__}: {e}>"
        ok = got == expected
        passed += ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] case {i:2d}: {text!r}")
        if not ok:
            print(f"         expected {expected!r}")
            print(f"         got      {got!r}")
    print(f"\nSCORE: {passed}/{len(CASES)}")
    return 0 if passed == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
