"""Persistence-layer errors."""


class StoreError(Exception):
    code: str = "store_error"


class NotFoundError(StoreError):
    code: str = "not_found"


class ConflictError(StoreError):
    code: str = "conflict"


class InvalidStateTransitionError(StoreError):
    code: str = "invalid_state_transition"
