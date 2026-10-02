#!/usr/bin/env python3
"""Generate the bcrypt hash for ADMIN_PASSWORD_HASH.

    python scripts/hash_password.py            # prompts for the password
    python scripts/hash_password.py --random   # creates a strong random password
"""

import getpass
import secrets
import sys

import bcrypt

if "--random" in sys.argv:
    password = secrets.token_urlsafe(18)
    print(f"Generated password (store it in your password manager): {password}", file=sys.stderr)
else:
    password = getpass.getpass("Admin password: ")
    if len(password) < 12:
        sys.exit("Use at least 12 characters.")
print(bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
