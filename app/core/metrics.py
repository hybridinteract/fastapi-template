"""
Prometheus Metrics Configuration.

Configures prometheus-fastapi-instrumentator to expose standard
HTTP metrics at the /metrics endpoint.

Metrics exposed:
- http_request_duration_seconds (histogram)
- http_requests_total (counter by method, path, status)
- http_request_size_bytes (histogram)
- http_response_size_bytes (histogram)
- http_requests_inprogress (gauge)
"""

from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    excluded_handlers=[
        "/health",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    ],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)
