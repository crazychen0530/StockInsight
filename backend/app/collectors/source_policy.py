"""Explicit, traceable upstream fallback before any business transaction."""

import logging

from app.collectors.akshare import AkShareProvider
from app.collectors.errors import ProviderError
from app.collectors.validator import MarketDataValidationError, validate_daily_prices
from app.repositories.source_policy import SourcePolicyRepository

logger = logging.getLogger("stockinsight.collectors.source_policy")


class PolicyProvider:
    def __init__(self, settings, *, calendar=None, factory=AkShareProvider):
        self.settings, self.calendar, self.factory = settings, calendar, factory
        self.daily_source = "akshare"

    def fetch_stocks(self):
        return self.factory(self.settings).fetch_stocks()

    def fetch_daily_prices(self, symbol, start, end):
        mode = SourcePolicyRepository(self.settings.source_policy_directory).read().mode
        interfaces = {
            "prefer_eastmoney": ("stock_zh_a_hist", "stock_zh_a_hist_tx"),
            "eastmoney": ("stock_zh_a_hist",),
            "tencent": ("stock_zh_a_hist_tx",),
        }[mode]
        for index, interface in enumerate(interfaces):
            provider = self.factory(
                self.settings.model_copy(update={"market_data_daily_interface": interface})
            )
            try:
                batch = provider.fetch_daily_prices(symbol, start, end)
                if batch.source != provider.daily_source:
                    raise ProviderError("provider_source_mismatch", "Provider source mismatch")
                batch = validate_daily_prices(
                    batch,
                    symbol,
                    start,
                    end,
                    trading_dates=self.calendar.days if self.calendar else None,
                )
                if not batch.records or (
                    self.calendar and not any(row.trade_date == end for row in batch.records)
                ):
                    raise ProviderError(
                        "daily_data_not_ready", "Daily market data is not ready", retryable=True
                    )
            except (ProviderError, MarketDataValidationError) as error:
                if index + 1 == len(interfaces) or error.code in {
                    "provider_dependency_missing",
                    "provider_source_mismatch",
                }:
                    raise
                logger.warning(
                    "Trying backup market source",
                    extra={
                        "event_data": {
                            "symbol": symbol,
                            "from_source": "akshare",
                            "to_source": "akshare_tx",
                            "reason": error.code,
                        }
                    },
                )
                continue
            self.daily_source = batch.source
            logger.info(
                "Market source selected",
                extra={
                    "event_data": {
                        "symbol": symbol,
                        "mode": mode,
                        "source": batch.source,
                        "fallback": index > 0,
                    }
                },
            )
            return batch
        raise AssertionError("Empty source policy")
