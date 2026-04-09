"""
core/exceptions.py — Custom exception classes for the application.
"""


class GeoAnalyzerError(Exception):
    """Base exception for the GeoSpatial Analyzer."""

    def __init__(self, message: str = "An error occurred in the GeoSpatial Analyzer"):
        self.message = message
        super().__init__(self.message)


class SiteNotFoundError(GeoAnalyzerError):
    """Raised when a site / H3 cell is not found in the database."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Site not found for identifier: {identifier}")


class InvalidWeightsError(GeoAnalyzerError):
    """Raised when user-provided weights are invalid."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid weights: {reason}")


class InvalidCoordinatesError(GeoAnalyzerError):
    """Raised when lat/lng coordinates are outside India bounds."""

    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng
        super().__init__(
            f"Coordinates ({lat}, {lng}) are outside India bounds "
            f"(lat: -8 to 37, lng: 68 to 97)"
        )


class InvalidH3IdError(GeoAnalyzerError):
    """Raised when an H3 grid ID has an invalid format."""

    def __init__(self, h3_id: str):
        self.h3_id = h3_id
        super().__init__(f"Invalid H3 grid ID format: {h3_id}")


class LLMError(GeoAnalyzerError):
    """Raised when an LLM call fails."""

    def __init__(self, provider: str, detail: str = ""):
        super().__init__(f"LLM error ({provider}): {detail}")


class GraphExecutionError(GeoAnalyzerError):
    """Raised when the LangGraph execution encounters a fatal error."""

    def __init__(self, node: str, detail: str = ""):
        self.node = node
        super().__init__(f"Graph execution error at node '{node}': {detail}")
