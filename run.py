#!/usr/bin/env python
"""
Run script for Elysium trading bot.
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from elysium.main import main

if __name__ == "__main__":
    main()