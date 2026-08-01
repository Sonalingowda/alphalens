"""Application-service-neutral exception contracts."""


class ServiceError(Exception):
    """Base class for Opportunity Intelligence service failures."""


class ServiceContractError(ServiceError):
    """Raised when service inputs or outputs violate a frozen contract."""


class PolicyUnavailableError(ServiceError):
    """Raised when an operation requires an unavailable approved policy."""


class ServiceUnavailableError(ServiceError):
    """Raised when a service cannot complete without fabricating output."""


class PipelineSuspendedError(ServiceError):
    """Raised when runtime governance suspends the affected scope."""

