"""
HERMES Adapter ROS2 Node — hybrid DDS face for the Odoo Adapter.

Runs alongside FastAPI in the same process. Exposes ROS2 services for
warehouse operations and stock management, and subscribes to mission state
to relay updates to Orion-LD (absorbing the ROS-FIWARE Bridge).

DDS stack: Vulcanexus Humble (eProsima Fast-DDS).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Optional

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy, HistoryPolicy
from std_msgs.msg import String, Int16, Header
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

# hermes_msgs service/message types (built from ros2_ws/src/hermes_msgs)
# NOTE: PushArticle was removed from the adapter in the HOST-COM cleanup —
# HOST-COM has no article master data concept and no caller ever invoked
# /hermes/articles/push. The .srv file in hermes_msgs is retained (deleting
# it would force a cross-workspace IDL rebuild for zero benefit).
from hermes_msgs.srv import (
    WarehousePick,
    WarehousePickStatus,
    WarehousePickCancel,
    ConsumeStock,
    ProduceStock,
)
from hermes_msgs.msg import InventoryUpdate
from builtin_interfaces.msg import Time

from .warehouse.base import WarehouseClient
from .odoo_client import OdooClient
from .orion_client import OrionClient

logger = logging.getLogger(__name__)


class HermesAdapterNode(Node):
    """
    ROS2 node that bridges DDS ↔ internal adapter clients.

    All service callbacks delegate to the *async* client methods. Because
    rclpy service callbacks run on the executor thread we use
    ``asyncio.run_coroutine_threadsafe`` to schedule work on the FastAPI
    event loop.
    """

    def __init__(
        self,
        odoo_client: OdooClient,
        orion_client: OrionClient,
        warehouse_client: WarehouseClient,
        event_loop: asyncio.AbstractEventLoop,
        *,
        node_name: str = "hermes_adapter",
        stock_location_id: int = 8,
        orion_context_url: str = "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld",
    ) -> None:
        super().__init__(node_name)
        self._odoo = odoo_client
        self._orion = orion_client
        self._warehouse = warehouse_client
        self._loop = event_loop
        self._stock_location_id = stock_location_id
        self._orion_context_url = orion_context_url

        # -- Warehouse services -----------------------------------------------
        self.create_service(
            WarehousePick,
            "/hermes/warehouse/pick",
            self._handle_warehouse_pick,
        )
        self.create_service(
            WarehousePickStatus,
            "/hermes/warehouse/status",
            self._handle_pick_status,
        )
        self.create_service(
            WarehousePickCancel,
            "/hermes/warehouse/cancel",
            self._handle_pick_cancel,
        )

        # -- Stock services ----------------------------------------------------
        self.create_service(
            ConsumeStock,
            "/hermes/stock/consume",
            self._handle_consume_stock,
        )
        self.create_service(
            ProduceStock,
            "/hermes/stock/produce",
            self._handle_produce_stock,
        )

        # -- Inventory update publisher ----------------------------------------
        self._inventory_pub = self.create_publisher(
            InventoryUpdate, "/hermes/inventory_updates", 10
        )

        # -- Mission state subscriber (absorbs ROS-FIWARE Bridge) -------------
        self.create_subscription(
            String,
            "/hermes/mission_state",
            self._handle_mission_state,
            10,
        )

        # -- Observability: /diagnostics + latched tray_state topic -----------
        # ARISE / standard ROS2 tooling expects every stateful node to publish
        # on /diagnostics (rqt_robot_monitor, Foxglove's diagnostic panel,
        # rviz diagnostic aggregator). The tray_state topic is a cheap latched
        # Int16 so late-joining subscribers immediately learn which tray the
        # adapter believes is at the pickup:
        #   -1 = unknown (refresh has not completed yet)
        #    0 = MP reports no tray at pickup
        #   >0 = tray number
        self._diag_pub = self.create_publisher(
            DiagnosticArray, "/diagnostics", 10,
        )
        latched_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
        )
        self._tray_state_pub = self.create_publisher(
            Int16, "/hermes/warehouse/tray_state", latched_qos,
        )
        self._last_published_tray: Optional[int] = None
        self.create_timer(1.0, self._publish_diagnostics)

        self.get_logger().info(
            "HermesAdapterNode ready — services: warehouse/pick, "
            "warehouse/status, warehouse/cancel, stock/consume, "
            "stock/produce | topics: /diagnostics, "
            "/hermes/warehouse/tray_state (latched)"
        )

    # ======================================================================
    # Helper: run async coroutine from the rclpy executor thread
    # ======================================================================

    def _run_async(self, coro: Any) -> Any:
        """Schedule *coro* on the FastAPI event loop and wait for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    # ======================================================================
    # Warehouse service handlers
    # ======================================================================

    def _handle_warehouse_pick(
        self,
        request: WarehousePick.Request,
        response: WarehousePick.Response,
    ) -> WarehousePick.Response:
        job_id = request.job_id or f"J-{uuid.uuid4().hex[:8]}"
        self.get_logger().info(
            f"WarehousePick: job={job_id} sku={request.sku} qty={request.quantity}"
        )
        try:
            result = self._run_async(
                self._warehouse.send_pick_order(job_id, request.sku, request.quantity)
            )
            response.success = result.success
            response.job_id = result.job_id
            response.error = result.error
        except Exception as exc:
            self.get_logger().error(f"WarehousePick failed: {exc}")
            response.success = False
            response.job_id = job_id
            response.error = str(exc)
        return response

    def _handle_pick_status(
        self,
        request: WarehousePickStatus.Request,
        response: WarehousePickStatus.Response,
    ) -> WarehousePickStatus.Response:
        try:
            status = self._run_async(
                self._warehouse.get_pick_status(request.job_id)
            )
            response.status = status.status
            response.slot = status.slot
            response.tray_ready = status.tray_ready
        except Exception as exc:
            self.get_logger().error(f"WarehousePickStatus failed: {exc}")
            response.status = "failed"
            response.slot = ""
            response.tray_ready = False
        return response

    def _handle_pick_cancel(
        self,
        request: WarehousePickCancel.Request,
        response: WarehousePickCancel.Response,
    ) -> WarehousePickCancel.Response:
        try:
            response.success = self._run_async(
                self._warehouse.cancel_pick(request.job_id)
            )
        except Exception as exc:
            self.get_logger().error(f"WarehousePickCancel failed: {exc}")
            response.success = False
        return response

    # ======================================================================
    # Stock service handlers
    # ======================================================================

    def _handle_consume_stock(
        self,
        request: ConsumeStock.Request,
        response: ConsumeStock.Response,
    ) -> ConsumeStock.Response:
        self.get_logger().info(
            f"ConsumeStock: project={request.project_id} "
            f"sku={request.sku} qty={request.quantity}"
        )
        try:
            result = self._run_async(
                self._odoo.consume_stock(
                    sku=request.sku,
                    quantity=request.quantity,
                    project_id=request.project_id,
                    location_id=self._stock_location_id,
                )
            )
            response.success = True
            response.remaining = float(result.get("remaining_qty", 0.0))

            # Update FIWARE InventoryItem
            self._run_async(self._sync_inventory_entity(request.sku, response.remaining))

            # Publish ROS2 inventory update
            self._publish_inventory_update(
                request.sku, response.remaining, 0.0, "", "mission_consume"
            )
        except Exception as exc:
            self.get_logger().error(f"ConsumeStock failed: {exc}")
            response.success = False
            response.remaining = 0.0
        return response

    def _handle_produce_stock(
        self,
        request: ProduceStock.Request,
        response: ProduceStock.Response,
    ) -> ProduceStock.Response:
        self.get_logger().info(
            f"ProduceStock: project={request.project_id} "
            f"sku={request.sku} qty={request.quantity}"
        )
        try:
            self._run_async(
                self._odoo.produce_stock(
                    sku=request.sku,
                    quantity=request.quantity,
                    project_id=request.project_id,
                    location_id=self._stock_location_id,
                )
            )
            response.success = True

            # Publish ROS2 inventory update
            self._publish_inventory_update(
                request.sku, 0.0, 0.0, "", "mission_produce"
            )
        except Exception as exc:
            self.get_logger().error(f"ProduceStock failed: {exc}")
            response.success = False
        return response

    # ======================================================================
    # Observability: /diagnostics + /hermes/warehouse/tray_state
    # ======================================================================

    def _publish_diagnostics(self) -> None:
        """1 Hz tick: publish DiagnosticArray + latched tray_state."""
        try:
            self._publish_diagnostics_inner()
        except Exception as exc:
            # Never let an exception kill the timer — log and continue.
            import traceback
            self.get_logger().error(
                f"_publish_diagnostics failed: {exc}\n{traceback.format_exc()}"
            )

    def _publish_diagnostics_inner(self) -> None:
        """Pulls state from the warehouse client via :meth:`get_state_summary`
        (default ``{}`` for backends with nothing to expose), plus the
        cached last health-check results for Odoo and Orion.
        """
        try:
            summary: dict = self._warehouse.get_state_summary() or {}
        except Exception as exc:
            self.get_logger().debug(f"get_state_summary failed: {exc}")
            summary = {}

        # --- Warehouse diagnostic status -----------------------------------
        current_tray = summary.get("current_tray")
        pending_jobs = int(summary.get("pending_jobs") or 0)
        last_refresh = summary.get("last_pickup_refresh")

        if not summary:
            level = DiagnosticStatus.WARN
            message = "no backend state (null or SOAP backend)"
            hardware_id = "n/a"
        elif current_tray is None:
            # Client is connected but refresh never succeeded — warn.
            level = DiagnosticStatus.WARN
            message = "current tray unknown — refresh_pickup_state has not completed"
            hardware_id = f"{summary.get('mp_host', '?')}:{summary.get('mp_port', '?')}"
        elif pending_jobs >= 10:
            level = DiagnosticStatus.ERROR
            message = f"{pending_jobs} pick jobs pending — possible leak"
            hardware_id = f"{summary.get('mp_host', '?')}:{summary.get('mp_port', '?')}"
        else:
            level = DiagnosticStatus.OK
            tray_label = "none" if current_tray == 0 else str(current_tray)
            message = f"tray {tray_label} at pickup, {pending_jobs} jobs pending"
            hardware_id = f"{summary.get('mp_host', '?')}:{summary.get('mp_port', '?')}"

        values = [
            KeyValue(key=str(k), value=str(v)) for k, v in summary.items()
        ]
        warehouse_status = DiagnosticStatus(
            level=level,
            name="hermes_adapter: warehouse",
            message=message,
            hardware_id=hardware_id,
            values=values,
        )

        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = ""
        array = DiagnosticArray(header=header, status=[warehouse_status])
        self._diag_pub.publish(array)

        # --- Latched tray_state topic (publish only on change) -------------
        tray_value: int = -1 if current_tray is None else int(current_tray)
        if tray_value != self._last_published_tray:
            prev = self._last_published_tray
            msg = Int16()
            msg.data = tray_value
            self._tray_state_pub.publish(msg)
            self._last_published_tray = tray_value
            self.get_logger().info(
                f"tray_state → {tray_value} (prev={prev})"
            )

    # ======================================================================
    # Mission state subscriber (absorbs ROS-FIWARE Bridge)
    # ======================================================================

    def _handle_mission_state(self, msg: String) -> None:
        """
        Relay mission state from DDS topic to Orion-LD.

        Same logic as the former ``ros_fiware_bridge.py``.
        """
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning(f"Invalid JSON on /hermes/mission_state: {msg.data}")
            return

        mission_id = payload.get("missionId")
        status = payload.get("status")
        if not mission_id or not status:
            self.get_logger().warning(f"Mission state missing missionId/status: {payload}")
            return

        self.get_logger().info(f"Relaying mission state → Orion: {mission_id} → {status}")
        try:
            update_attrs = {
                "status": {"type": "Property", "value": status},
                "message": {"type": "Property", "value": payload.get("message", "")},
                "@context": [self._orion_context_url],
            }
            self._run_async(
                self._orion.update_entity(mission_id, update_attrs, "Mission")
            )
        except Exception as exc:
            self.get_logger().error(f"Failed to relay mission state for {mission_id}: {exc}")

    # ======================================================================
    # Internal helpers
    # ======================================================================

    async def _sync_inventory_entity(self, sku: str, available: float) -> None:
        """Update the InventoryItem entity in Orion-LD after a stock change."""
        entity_id = f"urn:ngsi-ld:InventoryItem:{sku}"
        entity = {
            "id": entity_id,
            "type": "InventoryItem",
            "available": {"type": "Property", "value": available},
            "@context": [self._orion_context_url],
        }
        await self._orion.upsert_entity(entity)

    def _publish_inventory_update(
        self,
        sku: str,
        available: float,
        reserved: float,
        location: str,
        source: str,
    ) -> None:
        """Publish an InventoryUpdate message on the DDS topic."""
        msg = InventoryUpdate()
        msg.sku = sku
        msg.available = available
        msg.reserved = reserved
        msg.location = location
        msg.source = source
        now = self.get_clock().now().to_msg()
        msg.stamp = now
        self._inventory_pub.publish(msg)
