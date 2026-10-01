"""Create .env from .env.example with a fresh random SECRET_KEY (used by setup.bat).

Never overwrites an existing .env, so your saved password is safe.
"""
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"
example = ROOT / ".env.example"

if env_file.exists():
    print(".env already exists - leaving it unchanged.")
    sys.exit(0)

text = example.read_text(encoding="utf-8")
text = text.replace("SECRET_KEY=change-me-to-a-long-random-string", f"SECRET_KEY={secrets.token_urlsafe(50)}")
env_file.write_text(text, encoding="utf-8")
print("Created .env with a new random SECRET_KEY.")
