"""Test package for ml-nexus"""

from pinjected import design
from loguru import logger

# Set logger in design so all child modules can use it
__meta_design__ = design(
    logger=logger
)