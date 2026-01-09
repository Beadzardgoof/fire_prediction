"""
Simple test script to verify Google Earth Engine credentials.
Just reads the JSON from the filepath and tests initialization.
"""

import os
import json
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

print("=" * 60)
print("Google Earth Engine Credentials Test")
print("=" * 60)

# Get GEE_KEY (filepath to JSON)
gee_key_path = os.getenv('GEE_KEY')

print(f"\n1. Checking GEE_KEY:")
if not gee_key_path:
    print("   ✗ GEE_KEY not set")
    exit(1)

# Clean up the path - remove quotes and control characters
# Strip quotes if present
gee_key_path = gee_key_path.strip('"\'')
# Remove control characters (form feeds, newlines, etc.)
gee_key_path = ''.join(c for c in gee_key_path if ord(c) >= 32 or c in '\\/')
# Normalize path separators
gee_key_path = gee_key_path.replace('/', '\\')
gee_key_path = gee_key_path.strip()

print(f"   GEE_KEY (raw): {repr(os.getenv('GEE_KEY'))}")
print(f"   GEE_KEY (cleaned): {gee_key_path}")

# If path doesn't exist, try to find the JSON file automatically
if not os.path.isfile(gee_key_path):
    print(f"   ⚠ File does not exist at cleaned path, searching project directory...")
    # Try to find the JSON file in the project directory
    project_root = Path.cwd()
    json_files = list(project_root.glob('*.json'))
    if json_files:
        print(f"   Found JSON files:")
        for jf in json_files:
            print(f"     - {jf}")
            # Check if it looks like a service account key (has client_email field)
            try:
                with open(jf, 'r') as f:
                    test_data = json.load(f)
                    if 'client_email' in test_data and 'private_key' in test_data:
                        print(f"   ✓ Found valid service account key: {jf}")
                        gee_key_path = str(jf.resolve())
                        print(f"   → Using: {gee_key_path}")
                        break
            except:
                continue
    else:
        print(f"   ✗ No JSON files found in project directory: {project_root}")
        exit(1)

if not os.path.isfile(gee_key_path):
    print(f"   ✗ Still cannot find file!")
    exit(1)

print(f"   ✓ File exists: {gee_key_path}")

print(f"   ✓ File exists")

# Read JSON from file
print(f"\n2. Reading JSON from file:")
try:
    with open(gee_key_path, 'r') as f:
        key_data = json.load(f)
    
    print(f"   ✓ JSON loaded successfully")
    print(f"   Service account: {key_data.get('client_email', 'NOT FOUND')}")
    
    # Check required fields
    required = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
    missing = [f for f in required if f not in key_data]
    if missing:
        print(f"   ✗ Missing fields: {missing}")
        exit(1)
    else:
        print(f"   ✓ All required fields present")
        
except json.JSONDecodeError as e:
    print(f"   ✗ Invalid JSON: {e}")
    exit(1)
except Exception as e:
    print(f"   ✗ Error reading file: {e}")
    exit(1)

# Test Earth Engine initialization
print(f"\n3. Testing Earth Engine:")
try:
    import ee
    
    # Create credentials using email from JSON
    service_account_email = key_data['client_email']
    credentials = ee.ServiceAccountCredentials(service_account_email, gee_key_path)
    
    print(f"   ✓ Credentials created")
    
    # Initialize
    ee.Initialize(credentials)
    print(f"   ✓ Earth Engine initialized")
    
    # Test connection
    test = ee.Number(1).getInfo()
    print(f"   ✓ Connection test passed: {test}")
    
    print(f"\n   ✓✓✓ SUCCESS! Credentials are valid. ✓✓✓")
    
except ImportError:
    print(f"   ✗ earthengine-api not installed")
    print(f"   Install: pip install earthengine-api")
except Exception as e:
    print(f"   ✗ Error: {e}")
    if 'JWT' in str(e) or 'signature' in str(e):
        print(f"\n   JWT Signature Error - check that:")
        print(f"   1. The JSON file is not corrupted")
        print(f"   2. The service account is active in Google Cloud Console")
        print(f"   3. The key hasn't been regenerated/deleted")

print("\n" + "=" * 60)
