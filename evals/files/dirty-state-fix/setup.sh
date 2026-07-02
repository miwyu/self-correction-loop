#!/bin/sh
# Recreates the eval's starting state: a git repo whose HEAD holds the old
# v1 cart.py, with the current v2 cart.py left as an uncommitted change.
set -eu
cd "$(dirname "$0")"

rm -rf .git
git init -q -b main .

mv cart.py cart.py.v2
cat > cart.py <<'EOF'
"""Shopping-cart total with quantity discounts (v1, simple loop)."""


def total(items):
    subtotal = 0.0
    for price in items:
        subtotal += price
    if len(items) > 5:
        subtotal *= 0.9
    return round(subtotal, 2)
EOF

printf '__pycache__/\n.pytest_cache/\n' > .gitignore
git add cart.py test_cart.py setup.sh .gitignore
git -c user.name="fixture" -c user.email="fixture@example.invalid" \
    commit -qm "cart v1"

mv cart.py.v2 cart.py
echo "setup complete: HEAD = cart v1 (committed); working tree = cart v2 (uncommitted)"
git status --short
