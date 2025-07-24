#!/usr/bin/env python3
"""
Test script for Confluence API connectivity
"""

import os
import sys
import requests
import json
import base64
from datetime import datetime

def load_env_file(env_file_path):
    """Load environment variables from file"""
    env_vars = {}
    try:
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
        return env_vars
    except FileNotFoundError:
        print(f"❌ Environment file not found: {env_file_path}")
        return None

def test_confluence_api(base_url, email, token):
    """Test Confluence API connectivity and permissions using Basic Auth"""
    print("🔍 Testing Confluence API connectivity...")
    
    # Create Basic Auth header
    auth_string = f"{email}:{token}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json"
    }
    
    # Test 1: Basic connectivity
    print("\n1. Testing basic API connectivity...")
    try:
        response = requests.get(f"{base_url}/content", headers=headers, params={"limit": 1})
        if response.status_code == 200:
            print("✅ API connectivity successful")
        else:
            print(f"❌ API connectivity failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ API connectivity error: {str(e)}")
        return False
    
    # Test 2: Get user info
    print("\n2. Testing user permissions...")
    try:
        response = requests.get(f"{base_url}/user/current", headers=headers)
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Authenticated as: {user_data.get('displayName', 'Unknown')} ({user_data.get('email', 'No email')})")
        else:
            print(f"⚠️  Could not get user info: {response.status_code}")
    except Exception as e:
        print(f"⚠️  User info error: {str(e)}")
    
    # Test 3: List spaces
    print("\n3. Testing space access...")
    try:
        response = requests.get(f"{base_url}/space", headers=headers, params={"limit": 5})
        if response.status_code == 200:
            spaces_data = response.json()
            spaces = spaces_data.get('results', [])
            print(f"✅ Found {len(spaces)} accessible spaces:")
            for space in spaces[:3]:  # Show first 3 spaces
                print(f"   - {space.get('name', 'Unknown')} ({space.get('key', 'Unknown')})")
            if len(spaces) > 3:
                print(f"   ... and {len(spaces) - 3} more")
        else:
            print(f"❌ Could not list spaces: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Space listing error: {str(e)}")
        return False
    
    # Test 4: Get sample content
    print("\n4. Testing content retrieval...")
    try:
        response = requests.get(
            f"{base_url}/content",
            headers=headers,
            params={
                "limit": 5,
                "expand": "body.storage,space,ancestors"
            }
        )
        if response.status_code == 200:
            content_data = response.json()
            pages = content_data.get('results', [])
            print(f"✅ Retrieved {len(pages)} pages:")
            for page in pages[:3]:  # Show first 3 pages
                title = page.get('title', 'No title')
                space_key = page.get('space', {}).get('key', 'Unknown')
                print(f"   - {title} (Space: {space_key})")
            if len(pages) > 3:
                print(f"   ... and {len(pages) - 3} more")
        else:
            print(f"❌ Could not retrieve content: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Content retrieval error: {str(e)}")
        return False
    
    # Test 5: Check API rate limits
    print("\n5. Checking API rate limits...")
    try:
        # Make a few rapid requests to check rate limiting
        for i in range(3):
            response = requests.get(f"{base_url}/content", headers=headers, params={"limit": 1})
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Remaining']
                print(f"   Request {i+1}: {remaining} requests remaining")
            else:
                print(f"   Request {i+1}: Rate limit headers not found")
        print("✅ Rate limit check completed")
    except Exception as e:
        print(f"⚠️  Rate limit check error: {str(e)}")
    
    return True

def main():
    """Main function"""
    print("🧪 Confluence API Connectivity Test")
    print("=" * 40)
    
    # Load environment variables
    env_files = ['../.env.updated', '../.env', './.env.template']
    env_vars = None
    
    for env_file in env_files:
        if os.path.exists(env_file):
            env_vars = load_env_file(env_file)
            print(f"📋 Loaded environment from: {env_file}")
            break
    
    if not env_vars:
        print("❌ No environment file found. Please create .env file.")
        sys.exit(1)
    
    # Get Confluence configuration
    confluence_base = env_vars.get('CONFLUENCE_BASE')
    confluence_token = env_vars.get('CONFLUENCE_TOKEN')
    confluence_email = env_vars.get('CONFLUENCE_EMAIL')
    
    if not confluence_base or not confluence_token:
        print("❌ Missing CONFLUENCE_BASE or CONFLUENCE_TOKEN in environment file")
        sys.exit(1)
    
    if not confluence_email:
        print("❌ Missing CONFLUENCE_EMAIL in environment file")
        print("💡 Add CONFLUENCE_EMAIL=your-email@domain.com to your environment file")
        sys.exit(1)
    
    print(f"🔗 Testing Confluence instance: {confluence_base}")
    print(f"👤 Using email: {confluence_email}")
    
    # Run tests
    success = test_confluence_api(confluence_base, confluence_email, confluence_token)
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 All Confluence API tests passed!")
        print("✅ Ready for data ingestion")
    else:
        print("❌ Some tests failed. Please check your configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main() 