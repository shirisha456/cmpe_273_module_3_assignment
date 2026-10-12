import logging

import requests
from flask import Flask, jsonify, request

PORT = 8080
INVENTORY_URL = "http://127.0.0.1:8081/v1/inventory/check"
INVENTORY_TIMEOUT_SECONDS = 1

logging.basicConfig(level=logging.INFO, format="%(asctime)s [rest-order] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.post("/v1/orders")
def create_order():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or "item_id" not in body or "quantity" not in body:
        return jsonify(error="JSON body with item_id and quantity is required"), 400

    payload = {"item_id": body["item_id"], "quantity": body["quantity"]}
    try:
        response = requests.post(INVENTORY_URL, json=payload, timeout=INVENTORY_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        log.warning("inventory call timed out after %ss", INVENTORY_TIMEOUT_SECONDS)
        return jsonify(
            status="failed",
            error=f"inventory service timed out after {INVENTORY_TIMEOUT_SECONDS}s",
        ), 504
    except requests.exceptions.ConnectionError:
        log.warning("inventory service unreachable")
        return jsonify(status="failed", error="inventory service unavailable"), 503

    try:
        inventory = response.json()
    except ValueError:
        log.warning("inventory returned non-JSON response (%d)", response.status_code)
        return jsonify(status="failed", error="bad response from inventory service"), 502

    if response.status_code == 200:
        log.info("order accepted: %s", payload)
        return jsonify(status="accepted", order=payload, inventory=inventory), 200

    # 400 / 404 / 409 from inventory are passed through to the client.
    log.info("order rejected (%d): %s", response.status_code, inventory)
    return jsonify(status="rejected", order=payload, inventory=inventory), response.status_code


if __name__ == "__main__":
    log.info("starting on port %d (inventory timeout=%ss)", PORT, INVENTORY_TIMEOUT_SECONDS)
    app.run(host="127.0.0.1", port=PORT)
