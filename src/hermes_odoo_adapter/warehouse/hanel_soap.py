"""
Hanel vertical warehouse SOAP 1.1 client.

Communicates with the Hanel MP controller (MP 12N-S / MP 100D) via the
"Com" web service exposed at ``http://<MP-IP>/ws/com?wsdl``
(namespace ``http://main.jws.com.hanel.de``).

SOAP methods used
-----------------
- ``sendJobsReqV01``     — submit pick orders
- ``readAllJobsReqV01``  — poll order status
- ``deleteJobReqV01``    — cancel pending orders
- ``sendAPDReqV01``      — push article master data
- ``readAllAMDReqV01``   — read full inventory
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import ArticleInfo, PickResult, PickStatus, WarehouseClient

logger = logging.getLogger(__name__)


class HanelSoapError(Exception):
    """Raised when the Hanel controller returns a non-zero returnValue."""


class HanelSoapClient(WarehouseClient):
    """
    Async-friendly SOAP 1.1 client for the Hanel MP controller.

    ``zeep`` is synchronous, so every call is wrapped with
    ``asyncio.get_event_loop().run_in_executor(...)`` to avoid blocking
    the FastAPI event loop.
    """

    def __init__(self, wsdl_url: str, timeout: int = 10) -> None:
        self._wsdl_url = wsdl_url
        self._timeout = timeout
        self._client: Any = None  # zeep.Client
        self._service: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        self._client = await loop.run_in_executor(None, self._create_client)
        self._service = self._client.service
        logger.info("HanelSoapClient connected to %s", self._wsdl_url)

    def _create_client(self) -> Any:
        from zeep import Client
        from zeep.transports import Transport
        from requests import Session

        session = Session()
        session.timeout = self._timeout
        transport = Transport(session=session, timeout=self._timeout)
        return Client(wsdl=self._wsdl_url, transport=transport)

    async def close(self) -> None:
        if self._client and hasattr(self._client.transport, "session"):
            self._client.transport.session.close()
        self._client = None
        self._service = None
        logger.info("HanelSoapClient closed")

    async def health_check(self) -> bool:
        try:
            # A lightweight inventory read as a ping
            await self._run(self._service.readAllAMDReqV01)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Pick orders
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError)),
        reraise=True,
    )
    async def send_pick_order(
        self, job_id: str, sku: str, quantity: int
    ) -> PickResult:
        """
        Send a pick order via ``sendJobsReqV01``.

        The Hanel expects a list of job position objects. Each position
        describes one article to pick (operation ``+`` for outbound pick).
        """
        position = {
            "articleNumber": sku,
            "operation": "+",
            "nominalQuantity": quantity,
        }
        try:
            result = await self._run(
                self._service.sendJobsReqV01,
                jobNumber=job_id,
                positions=[position],
            )
            return_value = getattr(result, "returnValue", -1)
            if return_value != 0:
                msg = f"sendJobsReqV01 returned {return_value} for job {job_id}"
                logger.error(msg)
                return PickResult(success=False, job_id=job_id, error=msg)

            logger.info("Pick order submitted: job=%s sku=%s qty=%d", job_id, sku, quantity)
            return PickResult(success=True, job_id=job_id)
        except Exception as exc:
            logger.error("SOAP error sending pick order %s: %s", job_id, exc)
            return PickResult(success=False, job_id=job_id, error=str(exc))

    async def get_pick_status(self, job_id: str) -> PickStatus:
        """
        Poll ``readAllJobsReqV01(mode=1)`` and find the job by its number.

        Job status codes:
          0 = pending, 3 = completed
        Position status codes:
          0 = pending, 1 = done
        """
        try:
            result = await self._run(self._service.readAllJobsReqV01, mode=1)
            jobs = getattr(result, "jobs", []) or []
            for job in jobs:
                if getattr(job, "jobNumber", "") == job_id:
                    job_status = getattr(job, "jobStatus", 0)
                    positions = getattr(job, "positions", []) or []
                    pos_status = 0
                    slot = ""
                    if positions:
                        pos = positions[0]
                        pos_status = getattr(pos, "positionStatus", 0)
                        lift = getattr(pos, "liftNumber", "")
                        shelf = getattr(pos, "shelfNumber", "")
                        slot = f"L{lift}-S{shelf}" if lift and shelf else ""

                    if job_status == 3 and pos_status == 1:
                        return PickStatus(status="ready", slot=slot, tray_ready=True)
                    elif job_status == 3:
                        return PickStatus(status="presenting", slot=slot, tray_ready=False)
                    else:
                        return PickStatus(status="submitted", tray_ready=False)

            # Job not found — may have been completed and cleared
            return PickStatus(status="failed")
        except Exception as exc:
            logger.error("SOAP error polling pick status for %s: %s", job_id, exc)
            return PickStatus(status="failed")

    async def cancel_pick(self, job_id: str) -> bool:
        """Cancel a pending pick via ``deleteJobReqV01``."""
        try:
            result = await self._run(
                self._service.deleteJobReqV01, jobNumber=job_id
            )
            rv = getattr(result, "returnValue", -1)
            if rv == 0:
                logger.info("Pick order cancelled: %s", job_id)
                return True
            logger.warning("deleteJobReqV01 returned %d for %s", rv, job_id)
            return False
        except Exception as exc:
            logger.error("SOAP error cancelling pick %s: %s", job_id, exc)
            return False

    # ------------------------------------------------------------------
    # Article master data
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError)),
        reraise=True,
    )
    async def push_article(self, sku: str, name: str) -> bool:
        """Push a single article to Hanel via ``sendAPDReqV01``."""
        article = {
            "articleNumber": sku,
            "articleName": name,
        }
        try:
            result = await self._run(
                self._service.sendAPDReqV01, articles=[article]
            )
            rv = getattr(result, "returnValue", -1)
            if rv == 0:
                logger.info("Article pushed to Hanel: %s (%s)", sku, name)
                return True
            logger.warning("sendAPDReqV01 returned %d for %s", rv, sku)
            return False
        except Exception as exc:
            logger.error("SOAP error pushing article %s: %s", sku, exc)
            return False

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    async def read_all_inventory(self) -> list[ArticleInfo]:
        """Read the full inventory via ``readAllAMDReqV01``."""
        try:
            result = await self._run(self._service.readAllAMDReqV01)
            articles_raw = getattr(result, "articles", []) or []
            articles: list[ArticleInfo] = []
            for a in articles_raw:
                articles.append(
                    ArticleInfo(
                        article_number=getattr(a, "articleNumber", ""),
                        article_name=getattr(a, "articleName", ""),
                        quantity=float(
                            getattr(a, "inventoryAtStorageLocation", 0)
                        ),
                        compartment=str(getattr(a, "compartmentNumber", "")),
                        lift=str(getattr(a, "liftNumber", "")),
                        shelf=str(getattr(a, "shelfNumber", "")),
                        minimum_inventory=float(
                            getattr(a, "minimumInventory", 0)
                        ),
                    )
                )
            logger.info("Read %d articles from Hanel inventory", len(articles))
            return articles
        except Exception as exc:
            logger.error("SOAP error reading inventory: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    async def _run(self, method: Any, **kwargs: Any) -> Any:
        """Run a synchronous zeep call in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(method, **kwargs))
