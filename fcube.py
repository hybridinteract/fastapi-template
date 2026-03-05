#!/usr/bin/env python
"""
FCube CLI - Module Generator

Usage:
    python fcube.py startmodule <ModuleName>
    python fcube.py listmodules
"""

# Note: To use FCube CLI in this project, you need to have
# the fcube package installed or available in your path.
#
# For now, you can copy the fcube/ directory from the parent project
# or install it as a package.

try:
    from fcube.cli import app
    
    if __name__ == "__main__":
        app()
except ImportError:
    print("FCube CLI not found. Please install it or copy the fcube/ directory.")
    print("For module generation, use the FCube CLI from your main project.")
