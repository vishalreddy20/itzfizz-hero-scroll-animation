from __future__ import annotations

import importlib
from typing import Any

from fastapi import FastAPI

from app.services.runtime_config import (
    get_otel_exporter,
    get_otel_service_name,
    get_otel_prometheus_port,
    get_otel_otlp_endpoint,
    is_otel_enabled,
)


def configure_telemetry(app: FastAPI) -> None:
    if not is_otel_enabled():
        return

    try:
        resources_module = importlib.import_module("opentelemetry.sdk.resources")
        trace_module = importlib.import_module("opentelemetry.sdk.trace")
        trace_export_module = importlib.import_module("opentelemetry.sdk.trace.export")
        api_trace = importlib.import_module("opentelemetry.trace")
        instr_module = importlib.import_module("opentelemetry.instrumentation.fastapi")

        resource = resources_module.Resource.create({"service.name": get_otel_service_name()})
        tracer_provider = trace_module.TracerProvider(resource=resource)
        exporter = _build_trace_exporter()
        if exporter is not None:
            tracer_provider.add_span_processor(trace_export_module.BatchSpanProcessor(exporter))

        api_trace.set_tracer_provider(tracer_provider)
        instr_module.FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)

        _configure_metrics()
    except Exception:
        # Telemetry must never break API availability.
        return


def _build_trace_exporter() -> Any | None:
    exporter_name = get_otel_exporter()

    if exporter_name in {"otlp", "jaeger"}:
        otlp_mod = importlib.import_module("opentelemetry.exporter.otlp.proto.http.trace_exporter")
        return otlp_mod.OTLPSpanExporter(endpoint=get_otel_otlp_endpoint())

    if exporter_name == "console":
        console_mod = importlib.import_module("opentelemetry.sdk.trace.export")
        return console_mod.ConsoleSpanExporter()

    return None


def _configure_metrics() -> None:
    exporter_name = get_otel_exporter()
    if exporter_name not in {"prometheus", "otlp", "jaeger"}:
        return

    metrics_mod = importlib.import_module("opentelemetry.sdk.metrics")
    metrics_api = importlib.import_module("opentelemetry.metrics")

    if exporter_name == "prometheus":
        prom_mod = importlib.import_module("opentelemetry.exporter.prometheus")
        reader = prom_mod.PrometheusMetricReader()
    else:
        otlp_metric_mod = importlib.import_module("opentelemetry.exporter.otlp.proto.http.metric_exporter")
        metric_export_mod = importlib.import_module("opentelemetry.sdk.metrics.export")
        exporter = otlp_metric_mod.OTLPMetricExporter(endpoint=get_otel_otlp_endpoint())
        reader = metric_export_mod.PeriodicExportingMetricReader(exporter)

    provider = metrics_mod.MeterProvider(metric_readers=[reader])
    metrics_api.set_meter_provider(provider)

    if exporter_name == "prometheus":
        start_http_server = importlib.import_module("prometheus_client").start_http_server
        start_http_server(get_otel_prometheus_port())
