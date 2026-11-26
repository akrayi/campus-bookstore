"""Create local database credentials only if .env does not already exist."""
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / '.env'
try:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(f'POSTGRES_PASSWORD={secrets.token_hex(32)}\n')
except FileExistsError:
    print('Existing .env preserved. No credentials changed.')
else:
    print('Created ignored .env with a random password. Password was not printed.')
