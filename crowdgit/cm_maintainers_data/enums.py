from enum import Enum


class ScraperError(Enum):
    NO_ENV_VARS = "Missing environment variables"
    NO_MAINTAINER_FILE = "No maintainer file found"
    ANALYSIS_FAILED = "Failed to analyze maintainer file content"
    INVALID_RESPONSE = "Invalid response from analysis"
