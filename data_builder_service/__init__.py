"""Standalone web service wrapper for running data_builder jobs.

This service is intentionally separate from the main BatchTrack Flask app so that:
- it can run on a different port/process
- it can be started/stopped independently (e.g. in Replit workflows)
- it doesn't import the main app's extensions/config
"""

