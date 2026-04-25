"""Persistence-layer errors."""


class StoreError(Exception):
    code = "store_error"


class NotFoundError(StoreError):
    code = "not_found"


class ConflictError(StoreError):
    code = "conflict"


class InvalidStateTransitionError(StoreError):
    code = "invalid_state_transition"
