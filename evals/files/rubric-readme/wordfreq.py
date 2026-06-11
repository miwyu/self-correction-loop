#!/usr/bin/env python3
"""Count word frequencies in a text file."""
import argparse
import json
import re
from collections import Counter


def count_words(text, min_length=1, ignore_case=False):
    if ignore_case:
        text = text.lower()
    words = re.findall(r"[A-Za-z']+", text)
    return Counter(w for w in words if len(w) >= min_length)


def main():
    parser = argparse.ArgumentParser(
        description="Count word frequencies in a text file."
    )
    parser.add_argument("file", help="path to the text file")
    parser.add_argument(
        "--top", type=int, default=10, help="number of words to show (default: 10)"
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=1,
        help="ignore words shorter than this (default: 1)",
    )
    parser.add_argument(
        "--ignore-case", action="store_true", help="treat words case-insensitively"
    )
    parser.add_argument("--json", action="store_true", help="emit results as JSON")
    args = parser.parse_args()

    with open(args.file, encoding="utf-8") as f:
        text = f.read()
    counts = count_words(text, args.min_length, args.ignore_case).most_common(args.top)
    if args.json:
        print(json.dumps([{"word": w, "count": c} for w, c in counts], indent=2))
    else:
        for word, count in counts:
            print(f"{count:6d}  {word}")


if __name__ == "__main__":
    main()
