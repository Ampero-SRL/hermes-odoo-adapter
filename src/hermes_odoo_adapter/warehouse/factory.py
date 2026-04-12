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

    if backend == "hanel_hostcom":
        from .hanel_hostcom import HanelHostComClient

        host = getattr(settings, "hanel_hostcom_host", None)
        if not host:
            raise ValueError(
                "HANEL_HOSTCOM_HOST must be set when WAREHOUSE_BACKEND=hanel_hostcom"
            )
        client = HanelHostComClient(
            host=host,
            port=getattr(settings, "hanel_hostcom_port", 2200),
            elevator_num=getattr(settings, "hanel_elevator_num", 1),
            pickup_point=getattr(settings, "hanel_pickup_point", 1),
            sku_tray_map=getattr(settings, "hanel_sku_tray_map", {}) or {},
            default_tray=getattr(settings, "hanel_default_tray", 8),
        )
        logger.info(
            "Creating HanelHostComClient → %s:%d (elevator=%d, pickup=%d, default_tray=%d)",
            host,
            getattr(settings, "hanel_hostcom_port", 2200),
            getattr(settings, "hanel_elevator_num", 1),
            getattr(settings, "hanel_pickup_point", 1),
            getattr(settings, "hanel_default_tray", 8),
        )
        return client

    # Default: NullWarehouseClient
    from .null import NullWarehouseClient

    logger.info("Creating NullWarehouseClient (dev/test mode)")
    return NullWarehouseClient()
