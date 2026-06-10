import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from subtrack.app import server as app  # noqa: F401  (Vercel expects `app`)