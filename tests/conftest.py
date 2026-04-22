"""Pytest configuration to add project root to path."""
import sys
from pathlib import Path

# Add project root to path so we can import main and test_impact_calculator
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))