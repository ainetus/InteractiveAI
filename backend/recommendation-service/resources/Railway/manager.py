# backend/recommendation-service/resources/Railway/manager.py

import os
import requests
from api.manager.base_manager import BaseRecommendationManager
from settings import logger


class RailwayManager(BaseRecommendationManager):
    def __init__(self):
        # URL of our Flask brain's /recommendations endpoint
        # Set RL_AGENT_API_URL in .env to point at the Flask brain
        self.agent_api_url = os.environ.get(
            "RL_AGENT_API_URL",
            "http://host.docker.internal:5001/recommendations",
        )
        self.agent_api_token = os.environ.get("RL_AGENT_API_TOKEN", "")
        super().__init__()

    def get_recommendation(self, request_data):
        """
        Calls our Flask brain's /recommendations endpoint and returns
        the result in the format InteractiveAI expects.
        """
        headers = {"Content-Type": "application/json"}
        if self.agent_api_token:
            headers["Authorization"] = "Bearer " + self.agent_api_token

        try:
            response = requests.post(
                self.agent_api_url,
                json=request_data,
                headers=headers,
                timeout=10,
                verify=False,
            )
            recommendations = response.json()
            logger.info("Railway recommendations received: " + str(len(recommendations)))
            return recommendations

        except Exception as e:
            logger.error("Failed to get Railway recommendations: " + str(e))
            # Return a fallback so the UI doesn't break
            return [{
                "title":       "No recommendations available",
                "description": "Could not reach the simulation brain. Please try again.",
                "use_case":    "Railway",
                "agent_type":  "AI",
                "actions":     [{}],
                "kpis":        {},
            }]
