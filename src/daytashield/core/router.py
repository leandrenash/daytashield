"""Data routing based on validation results."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

from daytashield.core.result import ValidationResult, ValidationStatus


class RouteAction(str, Enum):
    """Actions that can be taken for routed data."""

    PASS = "pass"  # Send to destination
    REVIEW = "review"  # Send to review queue
    QUARANTINE = "quarantine"  # Isolate failed data
    RETRY = "retry"  # Attempt reprocessing
    DROP = "drop"  # Discard the data


class Route(BaseModel):
    """A routing rule with condition and action."""

    name: str = Field(..., description="Route name for identification")
    action: RouteAction = Field(..., description="Action to take")
    condition: Callable[[ValidationResult], bool] | None = Field(
        None, description="Custom condition function"
    )
    destination: str | None = Field(None, description="Destination identifier")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional route metadata")

    model_config = {"arbitrary_types_allowed": True}


class RoutingDecision(BaseModel):
    """The result of routing a validation result."""

    route: Route = Field(..., description="The matched route")
    result: ValidationResult = Field(..., description="The validation result")
    reason: str = Field(..., description="Why this route was selected")

    model_config = {"arbitrary_types_allowed": True}


class RouterConfig(BaseModel):
    """Configuration for the data router."""

    default_action: RouteAction = Field(
        RouteAction.QUARANTINE, description="Default action when no route matches"
    )
    include_warnings_in_review: bool = Field(
        True, description="Route warnings to review queue"
    )


class DataRouter:
    """Routes data based on validation results.

    The router examines validation results and determines where data should
    go: pass to destination, send to review, quarantine, etc.

    Default routing logic:
    - PASSED → PASS (send to destination)
    - WARNING → REVIEW (send to review queue) if configured
    - FAILED → QUARANTINE (isolate for investigation)
    - ERROR → QUARANTINE

    Example:
        >>> router = DataRouter()
        >>> result = pipeline.validate(data)
        >>> decision = router.route(result)
        >>> if decision.route.action == RouteAction.PASS:
        ...     send_to_destination(result.data)
        >>> elif decision.route.action == RouteAction.QUARANTINE:
        ...     quarantine(result.data, decision.reason)
    """

    def __init__(
        self,
        routes: list[Route] | None = None,
        config: RouterConfig | dict[str, Any] | None = None,
    ):
        """Initialize the router.

        Args:
            routes: Custom routes (checked before defaults)
            config: Router configuration
        """
        self.custom_routes: list[Route] = routes or []
        
        if config is None:
            self.config = RouterConfig()
        elif isinstance(config, dict):
            self.config = RouterConfig(**config)
        else:
            self.config = config

        # Set up default routes
        self._default_routes = self._create_default_routes()

    def _create_default_routes(self) -> list[Route]:
        """Create the default routing rules."""
        routes = [
            Route(
                name="pass_valid",
                action=RouteAction.PASS,
                condition=lambda r: r.status == ValidationStatus.PASSED,
            ),
            Route(
                name="quarantine_failed",
                action=RouteAction.QUARANTINE,
                condition=lambda r: r.status == ValidationStatus.FAILED,
            ),
            Route(
                name="quarantine_error",
                action=RouteAction.QUARANTINE,
                condition=lambda r: r.status == ValidationStatus.ERROR,
            ),
        ]

        # Add warning route based on config
        if self.config.include_warnings_in_review:
            routes.insert(
                1,
                Route(
                    name="review_warnings",
                    action=RouteAction.REVIEW,
                    condition=lambda r: r.status == ValidationStatus.WARNING,
                ),
            )
        else:
            routes.insert(
                1,
                Route(
                    name="pass_warnings",
                    action=RouteAction.PASS,
                    condition=lambda r: r.status == ValidationStatus.WARNING,
                ),
            )

        return routes

    def add_route(self, route: Route) -> DataRouter:
        """Add a custom route.

        Custom routes are checked before default routes.

        Args:
            route: The route to add

        Returns:
            Self for method chaining
        """
        self.custom_routes.append(route)
        return self

    def route(self, result: ValidationResult) -> RoutingDecision:
        """Determine where to route the data.

        Args:
            result: The validation result to route

        Returns:
            RoutingDecision with the selected route
        """
        # Check custom routes first
        for route in self.custom_routes:
            if route.condition and route.condition(result):
                return RoutingDecision(
                    route=route,
                    result=result,
                    reason=f"Matched custom route: {route.name}",
                )

        # Check default routes
        for route in self._default_routes:
            if route.condition and route.condition(result):
                return RoutingDecision(
                    route=route,
                    result=result,
                    reason=f"Matched default route: {route.name}",
                )

        # Fallback to default action
        fallback_route = Route(
            name="fallback",
            action=self.config.default_action,
        )
        return RoutingDecision(
            route=fallback_route,
            result=result,
            reason=f"No route matched, using default action: {self.config.default_action.value}",
        )

    def route_batch(self, results: list[ValidationResult]) -> dict[RouteAction, list[RoutingDecision]]:
        """Route multiple results and group by action.

        Args:
            results: List of validation results

        Returns:
            Dict mapping actions to lists of routing decisions
        """
        grouped: dict[RouteAction, list[RoutingDecision]] = {
            action: [] for action in RouteAction
        }

        for result in results:
            decision = self.route(result)
            grouped[decision.route.action].append(decision)

        return grouped

    def __repr__(self) -> str:
        return f"DataRouter(custom_routes={len(self.custom_routes)}, config={self.config})"
