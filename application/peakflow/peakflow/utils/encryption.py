#!/usr/bin/env python3
"""
PeakFlow Encryption Service
Shared encryption service for Garmin credentials across all modules.
"""
import os
import base64
import secrets
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from ..utils import get_logger

logger = get_logger("peakflow.utils.encryption")


class EncryptionError(Exception):
    """Custom exception for encryption-related errors."""
    pass


class EncryptionService:
    """Shared encryption service for Garmin credentials across all modules."""
    
    def __init__(self):
        """Initialize the encryption service with key from environment."""
        self.encryption_key = self._get_encryption_key()
        self.encryption_version = int(os.getenv('GARMIN_ENCRYPTION_VERSION', '1'))
        self.aes_gcm = AESGCM(self.encryption_key)
        logger.info(f"Encryption service initialized with version {self.encryption_version}")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using AES-256-GCM.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded ciphertext with version prefix
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            if not plaintext:
                raise ValueError("Cannot encrypt empty plaintext")
            
            # Convert string to bytes
            plaintext_bytes = plaintext.encode('utf-8')
            
            # Generate random 96-bit nonce for GCM
            nonce = secrets.token_bytes(12)
            
            # Encrypt with AES-256-GCM
            ciphertext = self.aes_gcm.encrypt(nonce, plaintext_bytes, None)
            
            # Combine version + nonce + ciphertext
            version_bytes = self.encryption_version.to_bytes(4, 'big')
            combined = version_bytes + nonce + ciphertext
            
            # Return base64-encoded result
            result = base64.b64encode(combined).decode('ascii')
            logger.debug("Successfully encrypted data")
            return result
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Failed to encrypt data: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.
        
        Args:
            ciphertext: Base64-encoded ciphertext with version prefix
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            if not ciphertext:
                raise ValueError("Cannot decrypt empty ciphertext")
            
            # Decode base64
            try:
                combined = base64.b64decode(ciphertext.encode('ascii'))
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding: {e}")
            
            # Extract version (first 4 bytes)
            if len(combined) < 20:  # 4 (version) + 12 (nonce) + 4 (minimum ciphertext)
                raise ValueError("Ciphertext too short")
            
            version = int.from_bytes(combined[:4], 'big')
            if version != self.encryption_version:
                logger.warning(f"Decrypting with version {version}, current version is {self.encryption_version}")
            
            # Extract nonce (next 12 bytes)
            nonce = combined[4:16]
            
            # Extract actual ciphertext (remaining bytes)
            actual_ciphertext = combined[16:]
            
            # Decrypt with AES-256-GCM
            plaintext_bytes = self.aes_gcm.decrypt(nonce, actual_ciphertext, None)
            
            # Convert bytes to string
            result = plaintext_bytes.decode('utf-8')
            logger.debug("Successfully decrypted data")
            return result
            
        except InvalidTag:
            logger.error("Decryption failed: Invalid authentication tag")
            raise EncryptionError("Decryption failed: Data may have been tampered with")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Failed to decrypt data: {e}")
    
    def _get_encryption_key(self) -> bytes:
        """
        Get encryption key from environment.
        
        Returns:
            32-byte encryption key
            
        Raises:
            EncryptionError: If key is invalid or missing
        """
        key_env = os.getenv('GARMIN_ENCRYPTION_KEY')
        if not key_env:
            raise EncryptionError(
                "GARMIN_ENCRYPTION_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets, base64; "
                "print(base64.b64encode(secrets.token_bytes(32)).decode())\""
            )
        
        try:
            # Decode base64 key
            key_bytes = base64.b64decode(key_env.encode('ascii'))
            
            # Validate key length (must be 32 bytes for AES-256)
            if len(key_bytes) != 32:
                raise ValueError(f"Key must be 32 bytes, got {len(key_bytes)} bytes")
            
            logger.info("Successfully loaded encryption key from environment")
            return key_bytes
            
        except Exception as e:
            raise EncryptionError(f"Invalid GARMIN_ENCRYPTION_KEY: {e}")


def generate_encryption_key() -> str:
    """
    Generate a new 256-bit encryption key.
    
    Returns:
        Base64-encoded 32-byte key suitable for GARMIN_ENCRYPTION_KEY
    """
    key_bytes = secrets.token_bytes(32)
    return base64.b64encode(key_bytes).decode('ascii')


def test_encryption_service() -> bool:
    """
    Test the encryption service with sample data.
    
    Returns:
        True if test passes, False otherwise
    """
    try:
        service = EncryptionService()
        
        # Test data
        test_data = "test_password_123"
        
        # Encrypt
        encrypted = service.encrypt(test_data)
        
        # Decrypt
        decrypted = service.decrypt(encrypted)
        
        # Verify
        success = test_data == decrypted
        if success:
            logger.info("Encryption service test passed")
        else:
            logger.error("Encryption service test failed: data mismatch")
        
        return success
        
    except Exception as e:
        logger.error(f"Encryption service test failed: {e}")
        return False


def main():
    """
    Command-line interface for encryption utilities.
    """
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        prog='peakflow.utils.encryption',
        description='PeakFlow encryption utilities for Garmin credentials',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        metavar='COMMAND'
    )
    
    # Generate key command
    generate_parser = subparsers.add_parser(
        'generate-key',
        help='Generate a new 256-bit encryption key for Garmin credentials'
    )
    generate_parser.add_argument(
        '--output-format',
        choices=['env', 'key-only'],
        default='env',
        help='Output format: env (with variable name) or key-only (just the key)'
    )
    
    # Test command
    test_parser = subparsers.add_parser(
        'test',
        help='Test the encryption service with sample data'
    )
    test_parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "generate-key":
        key = generate_encryption_key()
        
        if args.output_format == 'key-only':
            print(key)
        else:
            print("Generated new encryption key:")
            print(key)
            print()
            print("Add this to your .env file:")
            print(f"GARMIN_ENCRYPTION_KEY={key}")
        
    elif args.command == "test":
        if args.verbose:
            import logging
            logging.getLogger("peakflow.utils.encryption").setLevel(logging.DEBUG)
        
        success = test_encryption_service()
        if success:
            print("✓ Encryption service test passed")
            sys.exit(0)
        else:
            print("✗ Encryption service test failed")
            sys.exit(1)


if __name__ == "__main__":
    main()