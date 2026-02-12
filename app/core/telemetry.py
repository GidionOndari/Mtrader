from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

order_processing_duration_seconds = Histogram("order_processing_duration_seconds", "Order processing duration")
order_status_changes_total = Counter("order_status_changes_total", "Order status changes", ["status"])
mt5_connection_status = Gauge("mt5_connection_status", "MT5 connection status")
risk_incidents_total = Counter("risk_incidents_total", "Risk incidents", ["rule"])
backtest_jobs_running = Gauge("backtest_jobs_running", "Backtest jobs running")


def configure_telemetry(app=None, otlp_endpoint: str | None = None, service_name: str = "mtrader"):
    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)
    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    AsyncPGInstrumentor().instrument()
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = "mtrader"):
    return trace.get_tracer(name)
