"""
Analytics routes aggregator.

This module combines all analytics sub-routers into a single main analytics router
to maintain backward compatibility with the existing API structure.
"""

from fastapi import APIRouter

from . import activity, indicators, health, workout

# Create the main analytics router with the same prefix and tags as the original
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Include all sub-routers
router.include_router(activity.router)
router.include_router(indicators.router)
router.include_router(health.router)
router.include_router(workout.router)

# Export the router for use by the main application
__all__ = ["router"]
