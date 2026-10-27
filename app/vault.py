"""Authenticated encryption for persisted notification provider settings.

The installation key is deliberately separate from the database. This protects
database-only copies, not a compromised OS account or a backup containing both.
"""
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from .paths import private_directory, private_file

PREFIX = 'fernet:v1:'


class CredentialVault:
    def __init__(self, path, required=False):
        path = Path(path)
        private_directory(path.parent)
        if not path.exists():
            if required:
                raise ValueError('Provider credential key is missing; restore the original key before starting')
            # Exclusive creation avoids replacing a key created by another start.
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, 'wb') as file:
                    file.write(Fernet.generate_key())
                    file.flush()
                    os.fsync(file.fileno())
        private_file(path)
        try:
            self.cipher = Fernet(path.read_bytes().strip())
        except (ValueError, TypeError):
            raise ValueError('Provider credential key is invalid; restore the original key') from None

    def encrypt(self, value):
        return PREFIX + self.cipher.encrypt(value.encode()).decode('ascii')

    def decrypt(self, value):
        if not value.startswith(PREFIX):
            raise ValueError('Provider settings have not been encrypted')
        try:
            return self.cipher.decrypt(value[len(PREFIX):].encode('ascii')).decode('utf-8')
        except (InvalidToken, ValueError, UnicodeError):
            raise ValueError('Provider credentials could not be unlocked with this installation key') from None
