"""Compatibility shim for moved fault routes.

Route implementations now live in app.blueprints.faults.routes.
"""

from app.blueprints.faults.routes import faults_bp

__all__ = ["faults_bp"]