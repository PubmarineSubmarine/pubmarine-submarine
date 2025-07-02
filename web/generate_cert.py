#!/usr/bin/env python3
"""
Generate self-signed certificate for HTTPS development server.
Required for Gamepad API on Steam Deck and modern browsers.
"""

import os
import subprocess
import sys
from pathlib import Path

def generate_self_signed_cert():
    """Generate self-signed certificate for localhost."""
    cert_dir = Path("certs")
    cert_dir.mkdir(exist_ok=True)
    
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"
    
    if cert_file.exists() and key_file.exists():
        print("Certificate files already exist.")
        return str(cert_file), str(key_file)
    
    print("Generating self-signed certificate...")
    
    # Generate private key and certificate
    cmd = [
        "openssl", "req", "-x509", "-newkey", "rsa:4096", "-nodes",
        "-out", str(cert_file),
        "-keyout", str(key_file),
        "-days", "365",
        "-subj", "/C=US/ST=Dev/L=Local/O=PubmarineSubmarine/CN=localhost"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Certificate generated: {cert_file}")
        print(f"Private key generated: {key_file}")
        return str(cert_file), str(key_file)
    except subprocess.CalledProcessError as e:
        print(f"Error generating certificate: {e}")
        print("Make sure OpenSSL is installed on your system.")
        sys.exit(1)
    except FileNotFoundError:
        print("OpenSSL not found. Please install OpenSSL to generate certificates.")
        print("On Ubuntu/Debian: sudo apt install openssl")
        print("On macOS: brew install openssl")
        sys.exit(1)

if __name__ == "__main__":
    generate_self_signed_cert()