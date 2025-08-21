#!/usr/bin/env python3
"""
Quick diagnostic to check Alliance catalog file format
"""

def diagnose_file(filename):
    try:
        with open(filename, 'rb') as f:
            # Read first 20 bytes
            first_bytes = f.read(20)
            print(f"First 20 bytes: {first_bytes}")
            print(f"As hex: {first_bytes.hex()}")
            
        # Check file size
        import os
        size = os.path.getsize(filename)
        print(f"File size: {size:,} bytes")
        
        # Try to peek at first few lines as text
        try:
            with open(filename, 'r', encoding='latin-1') as f:
                print("\nFirst 3 lines (latin-1 encoding):")
                for i in range(3):
                    line = f.readline()
                    if not line:
                        break
                    print(f"Line {i+1}: {repr(line[:100])}")  # First 100 chars
        except Exception as e:
            print(f"Couldn't read as text: {e}")
            
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    diagnose_file("alliance_catalog.txt")