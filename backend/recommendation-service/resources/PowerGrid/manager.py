import os
from concurrent.futures import ThreadPoolExecutor

import requests
import urllib3
from api.manager.base_manager import BaseRecommendationManager
from settings import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Highest agent number read from the environment (RL_AGENT_<n>_API_URL)
MAX_AGENTS = 9


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
        }

    def get_agents(self):
        """The agents an operator can pick from, without their URL or token."""
        return [{"id": agent["id"], "name": agent["name"]} for agent in self.agents]

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
        requested = request_data.get("agents") or []
        agents = [a for a in self.agents if not requested or a["id"] in requested]
        # The agents get the request as before, without the platform's own field
        payload = {k: v for k, v in request_data.items() if k != "agents"}
        logger.info(
            "Getting recommendations from %s",
            ", ".join(agent["name"] for agent in agents) or "no agent",
        )
        if not agents:
            return []
        # In parallel: the operator waits for the slowest agent, not the sum
        with ThreadPoolExecutor(max_workers=len(agents)) as pool:
            results = list(
                pool.map(lambda agent: self._get_rl_parades(agent, payload), agents)
            )

        recommendations = []
        for agent, parades in zip(agents, results):
            for parade in parades:
                parade["agent_id"] = agent["id"]
                parade["agent_name"] = agent["name"]
                # The platform tells recommendations apart by title, and two
                # agents can propose the same one ("Continue")
                if len(self.agents) > 1:
                    parade["title"] = f"{parade.get('title', '')} · {agent['name']}"
                recommendations.append(parade)
        return recommendations

    def _get_rl_parades(self, agent, request_data):
        """Call an external RL agent API to get parade recommendations.

        Args:
            agent (dict): The agent to call, from self.agents
            request_data (dict): Full request payload with keys "event" and "context"

        Returns:
            list[dict]: List of parade recommendations, empty on failure
        """
        url = agent["url"]
        name = agent["name"]
        try:
            headers = {}
            if agent["token"]:
                headers["Authorization"] = f"Bearer {agent['token']}"
            response = requests.post(
                url,
                json=request_data,
                headers=headers,
                timeout=30,
                verify=False,  # SSL cert may not be trusted inside the container
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"{name} returned {len(data)} recommendation(s)")
            return data
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL error calling {name} ({url}): {e}")
            return []
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error calling {name} ({url}): {e} — response body: {e.response.text[:500] if e.response is not None else 'N/A'}")
            return []
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error calling {name} ({url}): {e}")
            return []
        except requests.exceptions.Timeout:
            logger.error(f"Timeout calling {name} ({url}) after 30s")
            return []
        except Exception as e:
            logger.error(f"Unexpected error calling {name} ({url}): {type(e).__name__}: {e}")
            return []
