from apiflask import HTTPError


class InvalidUseCase(HTTPError):
    status_code = 400
    message = 'Use case invalid'


class AgentError(Exception):
    """A recommendation agent could not be reached or gave no valid answer."""
