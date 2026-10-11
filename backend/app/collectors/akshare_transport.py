"""Bound the whole SDK call, including interfaces without a timeout argument."""

import json
import subprocess
import sys
from typing import Protocol

from app.collectors.errors import ProviderContractError, ProviderError, ProviderTimeoutError


class AkShareTransport(Protocol):
    def call(self, interface: str, parameters: dict[str, str | float], timeout: float) -> str:
        """Return a DataFrame split JSON envelope (columns/data); adapter-private."""
        ...


class SubprocessAkShareTransport:
    def call(self, interface: str, parameters: dict[str, str | float], timeout: float) -> str:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "app.collectors._akshare_worker"],
                input=json.dumps({"interface": interface, "parameters": parameters}),
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills and waits for the child; no abandoned network thread.
            raise ProviderTimeoutError() from None
        except OSError:
            raise ProviderError(
                "provider_unavailable", "Market data provider unavailable"
            ) from None
        if result.returncode == 10:
            raise ProviderTimeoutError()
        if result.returncode == 11:
            raise ProviderContractError()
        if result.returncode == 13:
            raise ProviderError(
                "provider_dependency_missing", "Install the market-data dependency extra"
            )
        if result.returncode != 0:
            raise ProviderError(
                "provider_unavailable", "Market data provider unavailable", retryable=True
            )
        return result.stdout
