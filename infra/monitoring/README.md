# Monitoring Infrastructure

The API exposes Prometheus-compatible metrics at `/metrics`.

OpenTelemetry-compatible instrumentation hooks are available in the application.

Production deployments can connect these signals to Prometheus, Grafana and an OTLP collector.
