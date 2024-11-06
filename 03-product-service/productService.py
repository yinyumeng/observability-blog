# product_service.py
from flask import Flask, jsonify, request
import requests
import random
import os
import psutil  # Library to collect system metrics

# OpenTelemetry Imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.metrics import CallbackOptions, Observation

# Flask app initialization
app = Flask(__name__)

OTLP = os.getenv("OTLP") if os.getenv("OTLP") is not None else "localhost"
USERSERVICE = os.getenv("USERSERVICE") if os.getenv("USERSERVICE") is not None else "localhost"

# Sample product data
products = [
    {"id": 1, "name": "Laptop", "purchased_by": [1, 2]},
    {"id": 2, "name": "Phone", "purchased_by": [1]}
]

# OpenTelemetry Initialization
resource = Resource(attributes={"service.name": "product-service"})

# Set up Tracer and Meter Providers
tracer_provider = TracerProvider(resource=resource)
trace.set_tracer_provider(tracer_provider)
span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="{}:55680".format(OTLP), insecure=True))
tracer_provider.add_span_processor(span_processor)

meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(endpoint="{}:55680".format(OTLP), insecure=True), export_interval_millis=1000)]
)
metrics.set_meter_provider(meter_provider)

# Create Tracer and Meter instances
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Instrument the Flask app
FlaskInstrumentor().instrument_app(app)

# Create metrics
request_count = meter.create_counter(
    name="request_count",
    description="Counts total requests by endpoint and status code",
    unit="1"
)

request_latency = meter.create_histogram(
    name="request_latency",
    description="Records the latency of requests",
    unit="ms"
)

# Callback functions for infrastructure metrics
def cpu_usage_callback(options: CallbackOptions):
    usage = psutil.cpu_percent()
    yield Observation(value=usage, attributes={"metric": "cpu_usage"})

def memory_usage_callback(options: CallbackOptions):
    memory_info = psutil.virtual_memory().percent
    yield Observation(value=memory_info, attributes={"metric": "memory_usage"})

def disk_io_read_callback(options: CallbackOptions):
    read_bytes = psutil.disk_io_counters().read_bytes
    yield Observation(value=read_bytes, attributes={"metric": "disk_io_read"})

def disk_io_write_callback(options: CallbackOptions):
    write_bytes = psutil.disk_io_counters().write_bytes
    yield Observation(value=write_bytes, attributes={"metric": "disk_io_write"})

# Register observable metrics
cpu_usage = meter.create_observable_gauge(
    name="cpu_usage",
    callbacks=[cpu_usage_callback],
    description="Tracks the CPU usage percentage",
    unit="%"
)

memory_usage = meter.create_observable_gauge(
    name="memory_usage",
    callbacks=[memory_usage_callback],
    description="Tracks the memory usage percentage",
    unit="%"
)

disk_io_read = meter.create_observable_gauge(
    name="disk_io_read",
    callbacks=[disk_io_read_callback],
    description="Tracks the total disk read bytes",
    unit="By"
)

disk_io_write = meter.create_observable_gauge(
    name="disk_io_write",
    callbacks=[disk_io_write_callback],
    description="Tracks the total disk write bytes",
    unit="By"
)

# Helper function to simulate error rate
def simulate_error_rate():
    """Simulate a 90% error rate."""
    return random.randint(0, 100) > 90

# Instrumented Endpoint: Get product details along with user info
@app.route('/products', methods=['GET'])
def get_products():
    with tracer.start_as_current_span("get_products") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", "/products")

        user_service_url = "http://{}:80/users".format(USERSERVICE)
        print(user_service_url)
        
        if simulate_error_rate():
            span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, "Service Unavailable"))
            request_count.add(1, {"endpoint": "/products", "status_code": 503})
            return jsonify({"error": "Service Unavailable"}), 503
        
        print("start getting response from user service")
        users = requests.get(user_service_url).json()  # Get users from User Service
        print("successfully getting response from user service")

        # Augment products with user information
        for product in products:
            product['purchased_by_users'] = [
                next((u for u in users if u["id"] == user_id), None)
                for user_id in product["purchased_by"]
            ]

        request_count.add(1, {"endpoint": "/products", "status_code": 200})
        return jsonify(products), 200

# Instrumented Endpoint: Get a single product by ID
@app.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    with tracer.start_as_current_span("get_product") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.route", "/products/<product_id>")
        span.set_attribute("product_id", product_id)

        if simulate_error_rate():
            span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, "Service Unavailable"))
            request_count.add(1, {"endpoint": "/products/<product_id>", "status_code": 503})
            return jsonify({"error": "Service Unavailable"}), 503

        product = next((p for p in products if p["id"] == product_id), None)
        if product:
            request_count.add(1, {"endpoint": "/products/<product_id>", "status_code": 200})
            return jsonify(product), 200

        span.set_status(trace.status.Status(trace.status.StatusCode.ERROR, "Product not found"))
        request_count.add(1, {"endpoint": "/products/<product_id>", "status_code": 404})
        return jsonify({"error": "Product not found"}), 404

# Main entry point
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)
