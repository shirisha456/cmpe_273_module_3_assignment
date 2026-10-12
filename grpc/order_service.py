import logging

import grpc
from flask import Flask, jsonify, request

import inventory_pb2
import inventory_pb2_grpc

PORT = 8090
INVENTORY_ADDRESS = "127.0.0.1:50051"
INVENTORY_DEADLINE_SECONDS = 1

# gRPC status from Inventory -> HTTP status returned to the Order Service client.
GRPC_TO_HTTP = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [grpc-order] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
channel = grpc.insecure_channel(INVENTORY_ADDRESS)
inventory_stub = inventory_pb2_grpc.InventoryServiceStub(channel)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.post("/v1/orders")
def create_order():
    body = request.get_json(silent=True)
    if (not isinstance(body, dict)
            or not isinstance(body.get("item_id"), str)
            or not isinstance(body.get("quantity"), int)
            or isinstance(body.get("quantity"), bool)):
        return jsonify(error="JSON body with item_id (string) and quantity (integer) is required"), 400

    inventory_request = inventory_pb2.InventoryRequest(item_id=body["item_id"], quantity=body["quantity"])
    order = {"item_id": inventory_request.item_id, "quantity": inventory_request.quantity}

    try:
        reply = inventory_stub.CheckInventory(inventory_request, timeout=INVENTORY_DEADLINE_SECONDS)
    except grpc.RpcError as error:
        code = error.code()
        log.warning("inventory RPC failed: %s - %s", code.name, error.details())
        http_status = GRPC_TO_HTTP.get(code, 502)
        status = "rejected" if http_status in (400, 404, 409) else "failed"
        return jsonify(status=status, order=order, grpc_status=code.name, error=error.details()), http_status

    log.info("order accepted: %s", order)
    inventory = {
        "available": reply.available,
        "item_id": reply.item_id,
        "requested_quantity": reply.requested_quantity,
        "available_quantity": reply.available_quantity,
    }
    return jsonify(status="accepted", order=order, grpc_status="OK", inventory=inventory), 200


if __name__ == "__main__":
    log.info("starting on port %d (inventory deadline=%ss)", PORT, INVENTORY_DEADLINE_SECONDS)
    app.run(host="127.0.0.1", port=PORT)
