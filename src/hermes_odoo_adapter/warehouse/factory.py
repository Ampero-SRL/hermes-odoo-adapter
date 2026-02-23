"""
Factory function to create the appropriate warehouse client based on settings.
"""
from __future__ import annotations

import logging

from .base import WarehouseClient

logger = logging.getLogger(__name__)


def create_warehouse_client(settings: object) -> WarehouseClient:
    """
    Instantiate the correct :class:`WarehouseClient` implementation.

    Parameters
    ----------
    settings
        Application settings object.  Expected attributes:
        - ``warehouse_backend`` — ``"hanel_soap"`` or ``"null"``
        - ``asrs_soap_url``     — WSDL URL (only when backend is ``hanel_soap``)
        - ``asrs_soap_timeout`` — request timeout in seconds

    Returns
    -------
    WarehouseClient
    """
    backend = getattr(settings, "warehouse_backend", "null")

    if backend == "hanel_soap":
        from .hanel_soap import HanelSoapClient

        url = getattr(settings, "asrs_soap_url", None)
        if not url:
            raise ValueError(
                "ASRS_SOAP_URL must be set when WAREHOUSE_BACKEND=hanel_soap"
            )
        timeout = getattr(settings, "asrs_soap_timeout", 10)
        logger.info("Creating HanelSoapClient → %s", url)
        return HanelSoapClient(wsdl_url=url, timeout=timeout)

    # Default: NullWarehouseClient
    from .null import NullWarehouseClient

    logger.info("Creating NullWarehouseClient (dev/test mode)")
    return NullWarehouseClient()
