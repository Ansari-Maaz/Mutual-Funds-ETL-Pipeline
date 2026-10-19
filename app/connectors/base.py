from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Iterable

class BaseConnector(ABC):
    source_id: str

    @abstractmethod
    def check_availability(self) -> dict[str, Any]: ...

    @abstractmethod
    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]: ...

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        return ()

    def extract_holdings(self, source_fund_id: str, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        return ()

    @abstractmethod
    def get_source_metadata(self) -> dict[str, Any]: ...
