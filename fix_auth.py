#!/usr/bin/env python3
"""Fix hardcoded BEARER_TOKEN references across frontend files."""

import os
import re

# Files to fix
files_to_fix = [
    "frontend/pages/02_Knowledge_Base.py",
    "frontend/pages/03_Plan.py", 
    "frontend/plan_app.py"
]

# Patterns to replace
replacements = [
    # Replace BEARER_TOKEN definition
    (r'BEARER_TOKEN = "test-token".*', '# Removed hardcoded token'),
    
    # Replace auth headers
    (r'headers=\{"Authorization": f"Bearer \{BEARER_TOKEN\}"\}', 'headers=auth.get_auth_headers()'),
    (r'\{"Authorization": f"Bearer \{BEARER_TOKEN\}"\}', 'auth.get_auth_headers()'),
]

for file_path in files_to_fix:
    if os.path.exists(file_path):
        print(f"Fixing {file_path}...")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Apply replacements
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        # Add auth import if not present
        if 'from auth import auth' not in content:
            content = content.replace('import streamlit as st', 'import streamlit as st\nfrom auth import auth')
        
        # Add require_auth if not present  
        if 'auth.require_auth()' not in content:
            # Add after API_BASE_URL line
            content = re.sub(
                r'(API_BASE_URL = [^\n]+)\n',
                r'\1\n\n# Require authentication\nauth.require_auth()\n',
                content
            )
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"Fixed {file_path}")
    else:
        print(f"File not found: {file_path}")

print("All files fixed!")
