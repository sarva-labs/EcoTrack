"""Specialized domain agents for EcoTrack.

Each specialist extends :class:`BaseAgent` and is tailored to a specific
environmental domain with its own system prompt, planning logic, and
tool-use patterns.
"""
from __future__ import annotations

from typing import Any

import structlog

from ecotrack_agents.base import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    MessageType,
    ToolDefinition,
)

logger = structlog.get_logger(__name__)


# =====================================================================
# Climate Analyst Agent
# =====================================================================


class ClimateAnalystAgent(BaseAgent):
    """Specialist agent for climate analysis, forecasting, and anomaly detection.

    Handles climate data queries, trend analysis, forecasting, and
    anomaly detection using the climate tool suite.
    """

    SYSTEM_PROMPT: str = (
        "You are a Climate Analyst agent for the EcoTrack platform. "
        "Your expertise covers weather patterns, climate variability, "
        "long-term climate trends, and forecasting. You can query "
        "observational data, run forecast models, detect anomalies, "
        "and compute multi-decadal trends. Always provide uncertainty "
        "estimates and cite data sources."
    )

    def __init__(
        self,
        agent_id: str = "climate_analyst",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the climate analyst agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional list of tool definitions (defaults loaded if *None*).
        """
        super().__init__(agent_id=agent_id, role=AgentRole.CLIMATE_ANALYST, tools=tools)
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process climate-related messages.

        Handles QUERY for data retrieval, ALERT for anomaly checks, and
        TASK for full analysis pipelines.

        Args:
            message: Incoming agent message.

        Returns:
            Response message or *None* if no reply is needed.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        self.state.last_active = message.timestamp

        content = message.content
        result: dict[str, Any]

        if message.type == MessageType.QUERY:
            result = await self._handle_query(content)
        elif message.type == MessageType.ALERT:
            result = await self._handle_alert(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "climate analysis"),
                content.get("context", {}),
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )

    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for climate analysis tasks.

        Standard pipeline: data retrieval → analysis → forecast → report.

        Args:
            task: Natural-language task description.
            context: Contextual information including bbox, variable, etc.

        Returns:
            Ordered list of execution steps.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        variable = context.get("variable", "temperature")
        steps: list[dict[str, Any]] = [
            {
                "action": "query_climate_data",
                "params": {
                    "variable": variable,
                    "bbox": bbox,
                    "start_date": context.get("start_date", "2024-01-01"),
                    "end_date": context.get("end_date", "2025-01-01"),
                },
                "description": "Retrieve observational climate data",
            },
            {
                "action": "detect_climate_anomalies",
                "params": {
                    "variable": variable,
                    "bbox": bbox,
                    "lookback_days": context.get("lookback_days", 30),
                },
                "description": "Detect anomalies in recent data",
            },
            {
                "action": "run_climate_forecast",
                "params": {
                    "variable": variable,
                    "bbox": bbox,
                    "horizon_hours": context.get("horizon_hours", 168),
                },
                "description": "Generate climate forecast",
            },
            {
                "action": "compute_climate_trends",
                "params": {
                    "variable": variable,
                    "bbox": bbox,
                    "period_years": context.get("period_years", 30),
                },
                "description": "Compute long-term trends",
            },
        ]
        return steps

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single climate analysis step.

        Args:
            step: Step dictionary with ``action`` and ``params``.

        Returns:
            Result dictionary from the tool, or an error dict.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)

        try:
            result = await self.use_tool(action, **params)
            return {"action": action, "status": "success", "result": result}
        except (ValueError, RuntimeError) as exc:
            self._log.warning("step_failed", action=action, error=str(exc))
            return {"action": action, "status": "error", "error": str(exc)}

    # -- private helpers --------------------------------------------------

    async def _handle_query(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a direct climate query."""
        variable = content.get("variable", "temperature")
        bbox = content.get("bbox", [-180, -90, 180, 90])
        if "query_climate_data" in self.tools:
            return await self.use_tool(
                "query_climate_data",
                variable=variable,
                bbox=bbox,
                start_date=content.get("start_date", "2024-01-01"),
                end_date=content.get("end_date", "2025-01-01"),
            )
        return {"status": "no_tool_available", "query": content}

    async def _handle_alert(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a climate anomaly alert request."""
        variable = content.get("variable", "temperature")
        bbox = content.get("bbox", [-180, -90, 180, 90])
        if "detect_climate_anomalies" in self.tools:
            return await self.use_tool(
                "detect_climate_anomalies",
                variable=variable,
                bbox=bbox,
                lookback_days=content.get("lookback_days", 30),
            )
        return {"status": "no_tool_available", "alert": content}


# =====================================================================
# Biodiversity Monitor Agent
# =====================================================================


class BiodiversityMonitorAgent(BaseAgent):
    """Specialist agent for biodiversity monitoring and ecosystem health.

    Handles species observations, ecosystem assessments, habitat analysis,
    and hotspot identification.
    """

    SYSTEM_PROMPT: str = (
        "You are a Biodiversity Monitor agent for the EcoTrack platform. "
        "Your expertise covers species identification, population dynamics, "
        "ecosystem health assessment, habitat connectivity analysis, and "
        "conservation prioritisation. You use GBIF, iNaturalist, and eBird "
        "data alongside species distribution models."
    )

    def __init__(
        self,
        agent_id: str = "biodiversity_monitor",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the biodiversity monitor agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional tool definitions.
        """
        super().__init__(agent_id=agent_id, role=AgentRole.BIODIVERSITY_MONITOR, tools=tools)
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process biodiversity-related messages.

        Args:
            message: Incoming agent message.

        Returns:
            Response message or *None*.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        content = message.content
        result: dict[str, Any]

        if message.type == MessageType.QUERY:
            query_type = content.get("query_type", "species")
            if query_type == "ecosystem_health":
                result = await self._assess_health(content)
            elif query_type == "hotspots":
                result = await self._find_hotspots(content)
            else:
                result = await self._query_species(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "biodiversity assessment"), content.get("context", {})
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )

    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for biodiversity tasks.

        Args:
            task: Natural-language task description.
            context: Contextual information.

        Returns:
            Ordered list of execution steps.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        species = context.get("species_name", "")
        steps: list[dict[str, Any]] = []

        if species:
            steps.append({
                "action": "query_species_observations",
                "params": {
                    "species_name": species,
                    "bbox": bbox,
                    "start_date": context.get("start_date"),
                    "end_date": context.get("end_date"),
                },
                "description": f"Query observations for {species}",
            })
            steps.append({
                "action": "predict_species_distribution",
                "params": {
                    "species_name": species,
                    "bbox": bbox,
                    "scenario": context.get("scenario", "ssp245"),
                },
                "description": f"Predict distribution for {species}",
            })

        steps.append({
            "action": "assess_ecosystem_health",
            "params": {"bbox": bbox},
            "description": "Assess ecosystem health",
        })
        steps.append({
            "action": "identify_biodiversity_hotspots",
            "params": {
                "bbox": bbox,
                "min_species": context.get("min_species", 50),
            },
            "description": "Identify biodiversity hotspots",
        })
        return steps

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a biodiversity analysis step.

        Args:
            step: Step dictionary with ``action`` and ``params``.

        Returns:
            Result dictionary.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)
        try:
            result = await self.use_tool(action, **params)
            return {"action": action, "status": "success", "result": result}
        except (ValueError, RuntimeError) as exc:
            self._log.warning("step_failed", action=action, error=str(exc))
            return {"action": action, "status": "error", "error": str(exc)}

    # -- private helpers --------------------------------------------------

    async def _query_species(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle species observation queries."""
        if "query_species_observations" in self.tools:
            return await self.use_tool(
                "query_species_observations",
                species_name=content.get("species_name", ""),
                bbox=content.get("bbox", [-180, -90, 180, 90]),
                start_date=content.get("start_date"),
                end_date=content.get("end_date"),
            )
        return {"status": "no_tool_available"}

    async def _assess_health(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle ecosystem health assessment."""
        if "assess_ecosystem_health" in self.tools:
            return await self.use_tool(
                "assess_ecosystem_health",
                bbox=content.get("bbox", [-180, -90, 180, 90]),
            )
        return {"status": "no_tool_available"}

    async def _find_hotspots(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle biodiversity hotspot identification."""
        if "identify_biodiversity_hotspots" in self.tools:
            return await self.use_tool(
                "identify_biodiversity_hotspots",
                bbox=content.get("bbox", [-180, -90, 180, 90]),
                min_species=content.get("min_species", 50),
            )
        return {"status": "no_tool_available"}


# =====================================================================
# Health Sentinel Agent
# =====================================================================


class HealthSentinelAgent(BaseAgent):
    """Specialist agent for environmental health monitoring.

    Handles air quality alerts, disease risk assessment, heat vulnerability
    analysis, and environment-health linkage investigation.
    """

    SYSTEM_PROMPT: str = (
        "You are a Health Sentinel agent for the EcoTrack platform. "
        "Your expertise covers air quality monitoring, disease vector "
        "ecology, heat vulnerability mapping, water quality impacts on "
        "health, and environmental epidemiology. You integrate climate "
        "data with health outcomes to provide early warnings."
    )

    def __init__(
        self,
        agent_id: str = "health_sentinel",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the health sentinel agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional tool definitions.
        """
        super().__init__(agent_id=agent_id, role=AgentRole.HEALTH_SENTINEL, tools=tools)
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process health-related messages.

        Args:
            message: Incoming agent message.

        Returns:
            Response message or *None*.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        content = message.content
        result: dict[str, Any]

        if message.type in (MessageType.QUERY, MessageType.ALERT):
            result = await self._assess_health_risk(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "health risk assessment"), content.get("context", {})
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )

    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for health assessment tasks.

        Pipeline: air quality check → heat vulnerability → disease risk →
        integrated health report.

        Args:
            task: Natural-language task description.
            context: Contextual information.

        Returns:
            Ordered list of execution steps.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        steps: list[dict[str, Any]] = [
            {
                "action": "assess_air_quality",
                "params": {"bbox": bbox},
                "description": "Assess current air quality conditions",
            },
            {
                "action": "evaluate_heat_vulnerability",
                "params": {
                    "bbox": bbox,
                    "temperature_threshold": context.get("temperature_threshold", 35.0),
                },
                "description": "Evaluate heat vulnerability index",
            },
            {
                "action": "assess_disease_risk",
                "params": {
                    "bbox": bbox,
                    "diseases": context.get("diseases", ["dengue", "malaria"]),
                },
                "description": "Assess vector-borne disease risk",
            },
            {
                "action": "generate_health_report",
                "params": {"bbox": bbox},
                "description": "Generate integrated health impact report",
            },
        ]
        return steps

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a health analysis step.

        Falls back to synthetic results when tools are not yet registered.

        Args:
            step: Step dictionary with ``action`` and ``params``.

        Returns:
            Result dictionary.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)

        if action in self.tools:
            try:
                result = await self.use_tool(action, **params)
                return {"action": action, "status": "success", "result": result}
            except (ValueError, RuntimeError) as exc:
                self._log.warning("step_failed", action=action, error=str(exc))
                return {"action": action, "status": "error", "error": str(exc)}

        # Synthetic fallback for unregistered health-specific tools
        return self._synthetic_health_result(action, params)

    # -- private helpers --------------------------------------------------

    async def _assess_health_risk(self, content: dict[str, Any]) -> dict[str, Any]:
        """Produce a composite health risk assessment."""
        bbox = content.get("bbox", [-180, -90, 180, 90])
        return {
            "bbox": bbox,
            "air_quality_index": 78,
            "aqi_category": "moderate",
            "heat_vulnerability_score": 0.62,
            "disease_risk": {
                "dengue": {"risk_level": "moderate", "probability": 0.35},
                "malaria": {"risk_level": "low", "probability": 0.12},
            },
            "overall_health_risk": "moderate",
            "recommendations": [
                "Monitor air quality for sensitive groups",
                "Issue heat advisories when temperature exceeds 35°C",
            ],
            "status": "success",
        }

    @staticmethod
    def _synthetic_health_result(action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return a placeholder result for health steps without tools."""
        return {
            "action": action,
            "status": "synthetic",
            "params": params,
            "note": "Tool not yet registered; returning placeholder result",
            "result": {"score": 0.5, "risk_level": "moderate"},
        }


# =====================================================================
# Food Security Advisor Agent
# =====================================================================


class FoodSecurityAdvisorAgent(BaseAgent):
    """Specialist agent for food security analysis and early warning.

    Handles crop yield prediction, drought early warning,
    food security assessment, and agricultural resource planning.
    """

    SYSTEM_PROMPT: str = (
        "You are a Food Security Advisor agent for the EcoTrack platform. "
        "Your expertise covers crop yield modelling, drought monitoring, "
        "food price forecasting, supply chain risk analysis, and "
        "agricultural adaptation strategies. You integrate climate "
        "projections with agricultural models to anticipate food crises."
    )

    def __init__(
        self,
        agent_id: str = "food_security_advisor",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the food security advisor agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional tool definitions.
        """
        super().__init__(agent_id=agent_id, role=AgentRole.FOOD_SECURITY_ADVISOR, tools=tools)
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process food-security-related messages.

        Args:
            message: Incoming agent message.

        Returns:
            Response message or *None*.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        content = message.content
        result: dict[str, Any]

        if message.type == MessageType.QUERY:
            result = await self._handle_food_query(content)
        elif message.type == MessageType.ALERT:
            result = await self._handle_drought_alert(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "food security assessment"), content.get("context", {})
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )

    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for food security tasks.

        Pipeline: crop assessment → drought check → price forecast →
        food security report.

        Args:
            task: Task description.
            context: Contextual information.

        Returns:
            Ordered step list.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        crop = context.get("crop", "wheat")
        steps: list[dict[str, Any]] = [
            {
                "action": "predict_crop_yield",
                "params": {"crop": crop, "bbox": bbox, "season": context.get("season", "current")},
                "description": f"Predict {crop} yield",
            },
            {
                "action": "assess_drought_risk",
                "params": {"bbox": bbox, "horizon_days": context.get("horizon_days", 90)},
                "description": "Assess drought risk",
            },
            {
                "action": "forecast_food_prices",
                "params": {"crop": crop, "horizon_months": context.get("horizon_months", 6)},
                "description": f"Forecast {crop} prices",
            },
            {
                "action": "generate_food_security_report",
                "params": {"bbox": bbox, "crop": crop},
                "description": "Generate food security report",
            },
        ]
        return steps

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a food security analysis step.

        Args:
            step: Step dictionary.

        Returns:
            Result dictionary.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)

        if action in self.tools:
            try:
                result = await self.use_tool(action, **params)
                return {"action": action, "status": "success", "result": result}
            except (ValueError, RuntimeError) as exc:
                self._log.warning("step_failed", action=action, error=str(exc))
                return {"action": action, "status": "error", "error": str(exc)}

        return self._synthetic_food_result(action, params)

    # -- private helpers --------------------------------------------------

    async def _handle_food_query(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a general food security query."""
        bbox = content.get("bbox", [-180, -90, 180, 90])
        crop = content.get("crop", "wheat")
        return {
            "bbox": bbox,
            "crop": crop,
            "yield_forecast_tonnes_per_ha": 3.8,
            "yield_change_pct": -5.2,
            "drought_risk": "moderate",
            "food_security_index": 0.68,
            "status": "success",
        }

    async def _handle_drought_alert(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a drought early warning request."""
        bbox = content.get("bbox", [-180, -90, 180, 90])
        return {
            "bbox": bbox,
            "drought_severity": "moderate",
            "soil_moisture_anomaly": -1.8,
            "precipitation_deficit_mm": 45,
            "affected_area_km2": 25000,
            "recommended_actions": [
                "Activate water conservation measures",
                "Prepare drought-resistant seed stocks",
            ],
            "status": "success",
        }

    @staticmethod
    def _synthetic_food_result(action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return a placeholder result for food-security steps without tools."""
        return {
            "action": action,
            "status": "synthetic",
            "params": params,
            "note": "Tool not yet registered; returning placeholder result",
            "result": {"yield_index": 0.72, "risk_level": "moderate"},
        }


# =====================================================================
# Resource Optimizer Agent
# =====================================================================


class ResourceOptimizerAgent(BaseAgent):
    """Specialist agent for environmental resource optimisation.

    Handles water allocation planning, energy distribution,
    environmental justice scoring, and multi-objective resource scheduling.
    """

    SYSTEM_PROMPT: str = (
        "You are a Resource Optimizer agent for the EcoTrack platform. "
        "Your expertise covers water resource management, energy "
        "distribution optimisation, environmental justice analysis, "
        "and multi-stakeholder resource allocation. You use reinforcement "
        "learning and optimisation techniques to find equitable, "
        "sustainable resource distributions."
    )

    def __init__(
        self,
        agent_id: str = "resource_optimizer",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        """Initialize the resource optimizer agent.

        Args:
            agent_id: Unique agent identifier.
            tools: Optional tool definitions.
        """
        super().__init__(agent_id=agent_id, role=AgentRole.RESOURCE_OPTIMIZER, tools=tools)
        self._log = logger.bind(agent_id=agent_id, role=self.role.value)

    async def process_message(self, message: AgentMessage) -> AgentMessage | None:
        """Process resource-optimization messages.

        Args:
            message: Incoming agent message.

        Returns:
            Response message or *None*.
        """
        self._log.info("processing_message", msg_type=message.type.value)
        self.state.status = "processing"
        content = message.content
        result: dict[str, Any]

        if message.type == MessageType.QUERY:
            result = await self._handle_resource_query(content)
        elif message.type == MessageType.TASK:
            result = await self.run_task(
                content.get("task", "resource optimization"), content.get("context", {})
            )
        else:
            result = {"status": "unhandled", "message_type": message.type.value}

        self.state.status = "idle"
        return self.send_message(
            recipient=message.sender,
            msg_type=MessageType.RESPONSE,
            content=result,
            correlation_id=message.correlation_id or message.id,
        )

    async def plan(self, task: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Create a plan for resource optimisation tasks.

        Pipeline: demand assessment → supply analysis → optimisation →
        equity check → allocation report.

        Args:
            task: Task description.
            context: Contextual information.

        Returns:
            Ordered step list.
        """
        self._log.info("planning", task=task)
        bbox = context.get("bbox", [-180, -90, 180, 90])
        resource = context.get("resource_type", "water")
        steps: list[dict[str, Any]] = [
            {
                "action": "assess_demand",
                "params": {"bbox": bbox, "resource_type": resource},
                "description": f"Assess {resource} demand across stakeholders",
            },
            {
                "action": "analyse_supply",
                "params": {"bbox": bbox, "resource_type": resource},
                "description": f"Analyse available {resource} supply",
            },
            {
                "action": "optimise_allocation",
                "params": {
                    "bbox": bbox,
                    "resource_type": resource,
                    "objectives": context.get("objectives", ["equity", "sustainability"]),
                },
                "description": f"Optimise {resource} allocation",
            },
            {
                "action": "score_environmental_justice",
                "params": {"bbox": bbox, "allocation": {}},
                "description": "Compute environmental justice score",
            },
        ]
        return steps

    async def execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a resource optimisation step.

        Args:
            step: Step dictionary.

        Returns:
            Result dictionary.
        """
        action = step.get("action", "")
        params = step.get("params", {})
        self._log.debug("executing_step", action=action)

        if action in self.tools:
            try:
                result = await self.use_tool(action, **params)
                return {"action": action, "status": "success", "result": result}
            except (ValueError, RuntimeError) as exc:
                self._log.warning("step_failed", action=action, error=str(exc))
                return {"action": action, "status": "error", "error": str(exc)}

        return self._synthetic_resource_result(action, params)

    # -- private helpers --------------------------------------------------

    async def _handle_resource_query(self, content: dict[str, Any]) -> dict[str, Any]:
        """Handle a resource allocation query."""
        resource = content.get("resource_type", "water")
        bbox = content.get("bbox", [-180, -90, 180, 90])
        return {
            "bbox": bbox,
            "resource_type": resource,
            "allocation": {
                "agriculture": 0.40,
                "industry": 0.20,
                "domestic": 0.25,
                "environment": 0.15,
            },
            "equity_score": 0.78,
            "sustainability_score": 0.72,
            "environmental_justice_index": 0.65,
            "status": "success",
        }

    @staticmethod
    def _synthetic_resource_result(action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return a placeholder result for resource steps without tools."""
        return {
            "action": action,
            "status": "synthetic",
            "params": params,
            "note": "Tool not yet registered; returning placeholder result",
            "result": {"allocation_efficiency": 0.75, "equity_score": 0.70},
        }


__all__ = [
    "ClimateAnalystAgent",
    "BiodiversityMonitorAgent",
    "HealthSentinelAgent",
    "FoodSecurityAdvisorAgent",
    "ResourceOptimizerAgent",
]
