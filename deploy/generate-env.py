"""Create a private production environment file without displaying secrets."""

import argparse
import re
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--domain", required=True)
parser.add_argument("--output", type=Path, default=Path(__file__).parent / ".env.production")
args = parser.parse_args()
if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", args.domain):
    parser.error("Use a hostname without a scheme, path, port, or whitespace.")
with args.output.open("x", encoding="utf-8") as stream:
    stream.write(
        f"DOMAIN={args.domain}\nPOSTGRES_PASSWORD={secrets.token_urlsafe(36)}\nSIGNING_SECRET={secrets.token_urlsafe(48)}\nOPERATIONS_TOKEN={secrets.token_urlsafe(48)}\nRELEASE_TAG=local\n"
    )
args.output.chmod(0o600)
print("Created the environment file. Keep it private and back it up separately.")
