from apiflask import HTTPError


class InvalidUseCase(HTTPError):
    status_code = 400
    message = 'Use case invalid'


class UpstreamAgentError(HTTPError):
    """The RL agent API could not be reached, or answered with an error.

    Distinct from "the agent ran and had nothing to recommend", which is an
    empty list and a success. Collapsing the two into an empty 200 makes an
    outage indistinguishable from a quiet grid: the caller waits on a spinner
    with nothing to retry and nothing in the UI to say why.
    """

    status_code = 502
    message = 'The recommendation agent is unavailable'
