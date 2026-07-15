from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to produce a consistent
    error response shape across the whole API.
    """
    response = exception_handler(exc, context)

    if response is not None:
        response.data = {
            "error": {
                "status_code": response.status_code,
                "details": response.data,
            }
        }

    return response
