import os
import time

import requests
import urllib3
from api.exceptions import UpstreamAgentError
from api.manager.base_manager import BaseRecommendationManager
from settings import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PowerGridManager(BaseRecommendationManager):
    """PowerGrid recomendation service

    Args:
        BaseRecommendationManager (): CAB recomendation service instance
    """

    def __init__(self):
        # Runtime value comes from the RL_AGENT_API_URL env var (set via
        # .secrets -> docker-compose.sh -> .env for local Docker, or extraEnv
        # for k8s). The fallback is a safe in-cluster default only.
        self.rl_agent_api_url = os.environ.get(
            "RL_AGENT_API_URL",
            "http://frontend:80/rl-api/recommendation",
        )
        self.rl_agent_api_token = os.environ.get("RL_AGENT_API_TOKEN", "")
        # A3S rollouts can take tens of seconds; 30s was too tight.
        self.rl_agent_api_timeout = float(
            os.environ.get("RL_AGENT_API_TIMEOUT", "120")
        )
        super().__init__()

    def get_recommendation(self, request_data):
        """Get IA agent recomendations

        Args:
            request_data (dict): A dictionary with keys "context" and "event"

        Returns:
            list[dict]: List of recomendations
        """
        logger.info("Getting RL agent recommendations from external API")
        return self._get_rl_parades(request_data)

    def _get_rl_parades(self, request_data):
        """Call the external RL agent API to get parade recommendations.

        Args:
            request_data (dict): Full request payload with keys "event" and "context"

        Returns:
            list[dict]: List of parade recommendations. Empty only when the
                agent ran and had nothing to propose.

        Raises:
            UpstreamAgentError: If the agent API could not be reached or
                answered with an error. Deliberately not swallowed into an
                empty list — see the exception's docstring.
        """
        try:
            headers = {}
            if self.rl_agent_api_token:
                headers["Authorization"] = f"Bearer {self.rl_agent_api_token}"
            started = time.monotonic()
            response = requests.post(
                self.rl_agent_api_url,
                json=request_data,
                headers=headers,
                timeout=self.rl_agent_api_timeout,
                verify=False,  # SSL cert may not be trusted inside the container
            )
            response.raise_for_status()
            data = response.json()
            elapsed = time.monotonic() - started
            if elapsed > self.rl_agent_api_timeout / 2:
                logger.warning(
                    "RL agent call took %.1fs of a %.0fs budget",
                    elapsed,
                    self.rl_agent_api_timeout,
                )
            else:
                logger.info("RL agent call took %.1fs", elapsed)
            logger.info(f"RL agent returned {len(data)} recommendation(s)")
            return data
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error calling RL agent API: {e}")
            raise UpstreamAgentError(
                message="Could not establish a secure connection to the "
                "recommendation agent"
            ) from e
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else 'N/A'
            logger.error(f"HTTP error calling RL agent API: {e} — response body: {body}")
            status = e.response.status_code if e.response is not None else None
            raise UpstreamAgentError(
                message=f"The recommendation agent returned an error "
                f"({status})" if status else
                "The recommendation agent returned an error",
                # The agent's own message goes in the detail rather than the
                # user-facing message: it is a Python traceback summary, not
                # something an operator can act on.
                detail={"upstream_status": status, "upstream_body": body},
            ) from e
        except requests.exceptions.Timeout as e:
            # Before ConnectionError: requests' Timeout subclasses it for the
            # connect-timeout case, so the narrower except has to come first.
            logger.error(
                "Timeout calling RL agent API (%s) after %.0fs",
                self.rl_agent_api_url,
                self.rl_agent_api_timeout,
            )
            raise UpstreamAgentError(
                message="The recommendation agent did not answer in time"
            ) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error calling RL agent API ({self.rl_agent_api_url}): {e}")
            raise UpstreamAgentError(
                message="Could not reach the recommendation agent"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error calling RL agent API: {type(e).__name__}: {e}")
            raise UpstreamAgentError(
                detail={"error": f"{type(e).__name__}: {e}"}
            ) from e
