#!/usr/bin/env python3
"""
Setup script for Confluence Q&A System
Makes the common module installable as a package
"""

from setuptools import setup, find_packages
import os

# Find all packages in func-app directory
packages = []
for root, dirs, files in os.walk('func-app'):
    if '__pycache__' not in root and '.pytest_cache' not in root:
        for dir_name in dirs:
            if dir_name not in ['__pycache__', '.pytest_cache']:
                package_path = os.path.join(root, dir_name)
                if os.path.exists(os.path.join(package_path, '__init__.py')):
                    packages.append(package_path.replace('/', '.'))

setup(
    name="confluence-qa-common",
    version="1.0.0",
    description="Common modules for Confluence Q&A System",
    author="Confluence Q&A Team",
    packages=packages,
    install_requires=[
        "azure-storage-blob",
        "gremlinpython",
        "python-dotenv==1.0.0",
        "networkx",
    ],
    python_requires=">=3.8",
    package_data={
        "": ["*.json", "*.yml", "*.yaml"],
    },
    include_package_data=True,
) 