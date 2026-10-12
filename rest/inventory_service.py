import logging
import os
import time

from flask import Flask, jsonify, request

PORT = 8081
INVENTORY = {"sku-123": 7}

# Failure test: start with INVENTORY_DELAY_SECONDS=2 to make every check slow.
DELAY_SECONDS = float(os.environ.get("INVENTORY_DELAY_SECONDS", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [rest-inventory] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


def parse_request(body):
    if not isinstance(body, dict):
        return None, None
    item_id = body.get("item_id")
    quantity = body.get("quantity")
    if not isinstance(item_id, str) or not item_id:
        return None, None
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return None, None
    return item_id, quantity


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.post("/v1/inventory/check")
def check_inventory():
    item_id, quantity = parse_request(request.get_json(silent=True))
    if item_id is None:
        return jsonify(error="item_id (non-empty string) and quantity (positive integer) are required"), 400

    if DELAY_SECONDS > 0:
        log.info("slow mode: sleeping %.1fs before answering", DELAY_SECONDS)
        time.sleep(DELAY_SECONDS)

    available_quantity = INVENTORY.get(item_id)
    if available_quantity is None:
        log.info("item_id=%s not found", item_id)
        return jsonify(available=False, item_id=item_id, error="item not found"), 404

    result = {
        "available": quantity <= available_quantity,
        "item_id": item_id,
        "requested_quantity": quantity,
        "available_quantity": available_quantity,
    }
    if not result["available"]:
        log.info("item_id=%s requested=%d available=%d -> insufficient", item_id, quantity, available_quantity)
        return jsonify({**result, "error": "insufficient quantity"}), 409

    log.info("item_id=%s requested=%d available=%d -> available", item_id, quantity, available_quantity)
    return jsonify(result), 200


if __name__ == "__main__":
    log.info("starting on port %d (delay=%.1fs)", PORT, DELAY_SECONDS)
    app.run(host="127.0.0.1", port=PORT)
