"""Middleware package entrypoint."""

from .registry import register_middleware

__all__ = ["register_middleware"]
