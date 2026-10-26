import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
from api.exceptions import AgentError
from api.manager.base_manager import BaseRecommendationManager
from settings import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Titles some agents still send in French, shown in English like the rest
TITLE_TRANSLATIONS = {"Poursuivre": "Continue"}


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


# Highest agent number read from the environment (RL_AGENT_<n>_API_URL)
MAX_AGENTS = 9
# Seconds an agent has to answer, unless RL_AGENT[_<n>]_TIMEOUT says otherwise.
# Keep the proxy in front of this service (nginx /cab_recommendation/) above
# the longest one, or it cuts the request first.
DEFAULT_AGENT_TIMEOUT = 30


class PowerGridManager(BaseRecommendationManager):
    """PowerGrid recomendation service

    Args:
        BaseRecommendationManager (): CAB recomendation service instance
    """

    def __init__(self):
        # Runtime values come from env vars (set via .secrets ->
        # docker-compose.sh -> .env for local Docker, or extraEnv for k8s).
        # Agent 1 keeps its original variables (RL_AGENT_API_URL, ...) and its
        # URL fallback is a safe in-cluster default only. Further agents are
        # optional and numbered from 2: RL_AGENT_2_API_URL, RL_AGENT_3_API_URL...
        # an unset URL means no such agent.
        self.agents = [
            self._agent_from_env(
                1, "", "http://frontend:80/rl-api/recommendation"
            )
        ] + [
            self._agent_from_env(number, f"_{number}")
            for number in range(2, MAX_AGENTS + 1)
        ]
        self.agents = [agent for agent in self.agents if agent["url"]]
        super().__init__()

    @staticmethod
    def _agent_from_env(number, suffix, default_url=""):
        return {
            "id": f"agent{number}",
            "name": os.environ.get(f"RL_AGENT{suffix}_NAME") or f"Agent {number}",
            "url": os.environ.get(f"RL_AGENT{suffix}_API_URL", default_url),
            "token": os.environ.get(f"RL_AGENT{suffix}_API_TOKEN", ""),
            "timeout": float(
                os.environ.get(f"RL_AGENT{suffix}_TIMEOUT") or DEFAULT_AGENT_TIMEOUT
            ),
            # How many recommendations to ask an agent that supports "num_reco":
            # when it is the only agent asked, and when it shares the screen with
            # others. Unset: the agent gets no "num_reco" and uses its default.
            "num_reco": _int_or_none(os.environ.get(f"RL_AGENT{suffix}_NUM_RECO")),
            "num_reco_shared": _int_or_none(
                os.environ.get(f"RL_AGENT{suffix}_NUM_RECO_SHARED")
            ),
        }

    def get_agents(self):
        """The agents an operator can pick from, without their URL or token."""
        return [{"id": agent["id"], "name": agent["name"]} for agent in self.agents]

    def select_agents(self, request_data):
        """The agents a request asks: its "agents" ids, all of them when absent or empty."""
        requested = request_data.get("agents") or []
        return [a for a in self.agents if not requested or a["id"] in requested]

    def get_recommendation(self, request_data):
        """Get IA agent recomendations

        Args:
            request_data (dict): A dictionary with keys "context" and "event",
                and optionally "agents", the ids of the agents to ask (all of
                them when absent or empty)

        Returns:
            list[dict]: List of recomendations, each tagged with the agent
                that made it
        """
        agents = self.select_agents(request_data)
        logger.info(
            "Getting recommendations from %s",
            ", ".join(agent["name"] for agent in agents) or "no agent",
        )
        if not agents:
            return []

        def ask(agent):
            try:
                return self.recommend_from(agent, request_data, alone=len(agents) == 1)
            except AgentError:
                return []

        # In parallel: the operator waits for the slowest agent, not the sum
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            results = list(pool.map(ask, agents))
        return [parade for parades in results for parade in parades]

    def recommend_from(self, agent, request_data, alone):
        """The recommendations of one agent, tagged with it.

        Args:
            agent (dict): The agent to ask, from self.agents
            request_data (dict): The request, as for get_recommendation
            alone (bool): Whether it is the only agent asked

        Returns:
            list[dict]: Its recommendations

        Raises:
            AgentError: The agent could not be reached or gave no valid answer
        """
        # The agents get the request as before, without the platform's own field
        payload = {k: v for k, v in request_data.items() if k != "agents"}
        parades = self._get_rl_parades(agent, self._payload_for(agent, payload, alone))

        seen_titles = {}
        for parade in parades:
            parade["agent_id"] = agent["id"]
            parade["agent_name"] = agent["name"]
            # The platform tells recommendations apart by title, and an
            # agent can propose two actions under the same one (Deep Expert,
            # rank 0 and 1 at the same substation): number the repeats
            title = parade.get("title", "")
            title = TITLE_TRANSLATIONS.get(title.strip(), title)
            seen_titles[title] = seen_titles.get(title, 0) + 1
            if seen_titles[title] > 1:
                title = f"{title} ({seen_titles[title]})"
            # ... and two agents can propose the same one ("Continue")
            if len(self.agents) > 1:
                title = f"{title} · {agent['name']}"
            parade["title"] = title
        return parades

    @staticmethod
    def _payload_for(agent, payload, alone):
        """The request for one agent: with its "num_reco" when it has one."""
        num_reco = agent["num_reco"] if alone else agent["num_reco_shared"]
        if num_reco is None:
            return payload
        return {**payload, "num_reco": num_reco}

    def _get_rl_parades(self, agent, request_data):
        """Call an external RL agent API to get parade recommendations.

        Args:
            agent (dict): The agent to call, from self.agents
            request_data (dict): Full request payload with keys "event" and "context"

        Returns:
            list[dict]: List of parade recommendations

        Raises:
            AgentError: On any failure, logged here
        """
        url = agent["url"]
        name = agent["name"]
        start = time.monotonic()
        try:
            headers = {}
            if agent["token"]:
                headers["Authorization"] = f"Bearer {agent['token']}"
            response = requests.post(
                url,
                json=request_data,
                headers=headers,
                timeout=agent["timeout"],
                verify=False,  # SSL cert may not be trusted inside the container
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError(f"expected a list, got {type(data).__name__}")
            logger.info(
                f"{name} returned {len(data)} recommendation(s) in {time.monotonic() - start:.1f}s"
            )
            return data
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error calling {name} ({url}): {e}")
            raise AgentError(name) from e
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error calling {name} ({url}): {e} — response body: {e.response.text[:500] if e.response is not None else 'N/A'}")
            raise AgentError(name) from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error calling {name} ({url}): {e}")
            raise AgentError(name) from e
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout calling {name} ({url}) after {agent['timeout']:g}s")
            raise AgentError(name) from e
        except Exception as e:
            logger.error(f"Unexpected error calling {name} ({url}): {type(e).__name__}: {e}")
            raise AgentError(name) from e
