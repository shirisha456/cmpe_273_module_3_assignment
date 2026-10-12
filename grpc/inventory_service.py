import logging
import os
import time
from concurrent import futures

import grpc

import inventory_pb2
import inventory_pb2_grpc

PORT = 50051
INVENTORY = {"sku-123": 7}

# Failure test: start with INVENTORY_DELAY_SECONDS=2 to make every check slow.
DELAY_SECONDS = float(os.environ.get("INVENTORY_DELAY_SECONDS", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [grpc-inventory] %(message)s")
log = logging.getLogger(__name__)


class InventoryService(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckInventory(self, request, context):
        item_id = request.item_id
        quantity = request.quantity

        if not item_id or quantity <= 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "item_id (non-empty) and quantity (positive) are required")

        if DELAY_SECONDS > 0:
            log.info("slow mode: sleeping %.1fs before answering", DELAY_SECONDS)
            time.sleep(DELAY_SECONDS)

        available_quantity = INVENTORY.get(item_id)
        if available_quantity is None:
            log.info("item_id=%s not found", item_id)
            context.abort(grpc.StatusCode.NOT_FOUND, f"item {item_id} not found")

        if quantity > available_quantity:
            log.info("item_id=%s requested=%d available=%d -> insufficient", item_id, quantity, available_quantity)
            context.abort(grpc.StatusCode.FAILED_PRECONDITION,
                          f"insufficient quantity: requested {quantity}, available {available_quantity}")

        log.info("item_id=%s requested=%d available=%d -> available", item_id, quantity, available_quantity)
        return inventory_pb2.InventoryResponse(
            available=True,
            item_id=item_id,
            requested_quantity=quantity,
            available_quantity=available_quantity,
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryService(), server)
    server.add_insecure_port(f"127.0.0.1:{PORT}")
    server.start()
    log.info("starting on port %d (delay=%.1fs)", PORT, DELAY_SECONDS)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
