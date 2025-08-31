import os
import sys

# Ensure the repository root is on sys.path so `now_playing` is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


