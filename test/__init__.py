"""Test package for ml-nexus"""

from pinjected import design
from loguru import logger

# Set logger in design so all child modules can use it
__design__ = design(logger=logger)

if __name__ == '__main__':
    import sys
    for item in sys.path:
        print(item)