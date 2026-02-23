"""
Abstract warehouse client interface.

Any storage system (Hanel, Kardex, manual shelves, etc.) implements this
interface so the rest of the adapter remains storage-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PickResult:
    """Result of submitting a pick order to the warehouse."""
    success: bool
    job_id: str
    error: str = ""


@dataclass
class PickStatus:
    """Current status of a previously submitted pick order."""
    status: str  # submitted | presenting | ready | failed
    slot: str = ""
    tray_ready: bool = False


@dataclass
class ArticleInfo:
    """Single article record from the warehouse inventory."""
    article_number: str
    article_name: str
    quantity: float
    compartment: str = ""
    lift: str = ""
    shelf: str = ""
    minimum_inventory: float = 0.0


class WarehouseClient(ABC):
    """Abstract base class for warehouse/ASRS backends."""

    @abstractmethod
    async def connect(self) -> None:
        """Initialise connection to the warehouse controller."""

    @abstractmethod
    async def close(self) -> None:
        """Tear down connection gracefully."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the warehouse controller is reachable."""

    @abstractmethod
    async def send_pick_order(
        self, job_id: str, sku: str, quantity: int
    ) -> PickResult:
        """
        Submit a pick order (present tray for the given SKU).

        Parameters
        ----------
        job_id : str
            Unique order identifier (e.g. ``{missionId}-{shortUUID}``).
        sku : str
            Article / SKU code.
        quantity : int
            Nominal quantity to pick.

        Returns
        -------
        PickResult
        """

    @abstractmethod
    async def get_pick_status(self, job_id: str) -> PickStatus:
        """Poll the status of a previously submitted pick order."""

    @abstractmethod
    async def cancel_pick(self, job_id: str) -> bool:
        """Cancel a pending pick order.  Returns True on success."""

    @abstractmethod
    async def push_article(self, sku: str, name: str) -> bool:
        """
        Push article master data to the warehouse (bootstrap / new product).

        Returns True on success.
        """

    @abstractmethod
    async def read_all_inventory(self) -> list[ArticleInfo]:
        """Read the complete inventory from the warehouse controller."""
