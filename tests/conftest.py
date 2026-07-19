"""Shared test setup: isolate preferences from any real user config."""

import os
import tempfile

# Point MarkStar's config at a throwaway file for the whole test session, so
# tests that toggle theme/mouse/formatting never overwrite ~/.config/markstar.
os.environ["MARKSTAR_CONFIG"] = os.path.join(
    tempfile.gettempdir(), "markstar-test-config.toml"
)
