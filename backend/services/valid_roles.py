# backend/services/valid_roles.py
"""Roles válidos do sistema — single source of truth."""

VALID_ROLES = frozenset({'admin', 'operator', 'financial', 'viewer'})
