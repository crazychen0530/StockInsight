"""Public safe provider failures, compatible with the existing error handler."""

from app.core.errors import ApplicationError


class ProviderError(ApplicationError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(code, message, status_code=503)
        self.retryable = retryable


class ProviderTimeoutError(ProviderError):
    def __init__(self) -> None:
        super().__init__("provider_timeout", "Market data provider timed out", retryable=True)


class ProviderContractError(ProviderError):
    def __init__(self) -> None:
        super().__init__("provider_contract_error", "Market data provider contract changed")
