"""Pinjected configuration for test module"""

from pinjected import design
from ml_nexus import load_env_design
from loguru import logger
from ml_nexus.event_bus_util import handle_ml_nexus_system_call_events__simple

# This file provides the design configuration for the test module
# It will be picked up by MetaContext when running tests
# load_env_design already includes all ml_nexus defaults
# We use overrides to properly handle the IProxy nature of load_env_design
test_defaults = design(
    logger=logger,
    ml_nexus_system_call_event_bus=handle_ml_nexus_system_call_events__simple,
)

__design__ = load_env_design + test_defaults