"""
PGP encryption utilities for VNSH
Encrypts LPA codes using customer-provided public keys
"""

import pgpy
from pgpy.constants import PubKeyAlgorithm, SymmetricKeyAlgorithm, CompressionAlgorithm


def encrypt_message(plaintext: str, public_key_armor: str) -> str:
    """
    Encrypt a message using a PGP public key.

    Args:
        plaintext: The message to encrypt (e.g., the LPA code)
        public_key_armor: ASCII-armored PGP public key

    Returns:
        ASCII-armored encrypted message

    Raises:
        ValueError: If the public key is invalid
    """
    try:
        # Load the public key
        pub_key, _ = pgpy.PGPKey.from_blob(public_key_armor)

        # Create the message
        message = pgpy.PGPMessage.new(plaintext)

        # Encrypt with the public key
        encrypted = pub_key.encrypt(message)

        return str(encrypted)

    except Exception as e:
        raise ValueError(f"Failed to encrypt with PGP key: {str(e)}")


def validate_public_key(public_key_armor: str) -> bool:
    """
    Validate that a string is a valid PGP public key.

    Args:
        public_key_armor: ASCII-armored PGP public key

    Returns:
        True if valid, False otherwise
    """
    if not public_key_armor:
        return False

    if not public_key_armor.strip().startswith('-----BEGIN PGP PUBLIC KEY BLOCK-----'):
        return False

    try:
        key, _ = pgpy.PGPKey.from_blob(public_key_armor)
        # Check it's actually a public key (not private)
        return key.is_public
    except Exception:
        return False
