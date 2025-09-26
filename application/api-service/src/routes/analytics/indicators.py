"""
User indicators management endpoints.
"""

from datetime import datetime, timezone, date
from fastapi import APIRouter, Depends, HTTPException, status, Request
import structlog

from ...models.responses import UserIndicatorsResponse
from ...models.requests import UserIndicatorsUpdateRequest
from ...middleware.auth import get_current_user
from ...middleware.logging import audit_logger
from ...database import User
from ...database import get_elasticsearch_storage
from peakflow import DataType, QueryFilter

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/user/indicators", response_model=UserIndicatorsResponse,
             operation_id="update_user_indicators",
             description="Update user fitness indicators and thresholds.")
async def update_user_indicators(
    request: Request,
    indicators_request: UserIndicatorsUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> UserIndicatorsResponse:
    """Update user fitness indicators and thresholds."""

    try:
        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)

        # Get current indicators if they exist
        current_query = QueryFilter()
        current_query.add_term_filter("user_id", user_id)
        current_query.set_pagination(limit=1)

        existing_indicators = storage.search(DataType.USER_INDICATOR, current_query)

        # Build update data from request (only include non-None values)
        update_data = {
            "user_id": user_id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Add all non-None values from the request
        for field, value in indicators_request.dict(exclude_none=True).items():
            if field == "birth_date" and value:
                # Convert date to ISO string for Elasticsearch
                update_data[field] = value.isoformat()
            else:
                update_data[field] = value

        # If existing indicators, update them; otherwise create new
        if existing_indicators:
            # Merge with existing data
            existing_data = existing_indicators[0]
            existing_data.update(update_data)
            update_data = existing_data

        # Store/update in Elasticsearch
        document_id = user_id  # Use user_id as document ID for upsert
        success = storage.index_document(DataType.USER_INDICATOR, document_id, update_data)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user indicators"
            )

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="user_indicators_updated",
            user_id=current_user.id,
            details={
                "fields_updated": list(indicators_request.dict(exclude_none=True).keys()),
                "total_fields": len(update_data)
            },
        )

        # Return response
        response_data = {
            "user_id": user_id,
            "updated_at": datetime.fromisoformat(update_data["updated_at"])
        }

        # Add all indicator fields to response
        for field in UserIndicatorsResponse.__fields__.keys():
            if field in ["user_id", "updated_at"]:
                continue
            if field in update_data:
                if field == "birth_date" and isinstance(update_data[field], str):
                    # Convert ISO string back to date
                    response_data[field] = date.fromisoformat(update_data[field])
                else:
                    response_data[field] = update_data[field]

        return UserIndicatorsResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "User indicators update error",
            user_id=getattr(current_user, 'id', 'unknown'),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user indicators",
        )


@router.get("/user/indicators", response_model=UserIndicatorsResponse,
            operation_id="get_user_indicators",
            description="Get current user fitness indicators and thresholds.")
async def get_user_indicators(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> UserIndicatorsResponse:
    """Get current user fitness indicators and thresholds."""

    try:
        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)

        # Query user indicators
        indicators_query = QueryFilter()
        indicators_query.add_term_filter("user_id", user_id)
        indicators_query.set_pagination(limit=1)

        indicators = storage.search(DataType.USER_INDICATOR, indicators_query)

        # Build response
        response_data = {
            "user_id": user_id,
            "updated_at": datetime.now(timezone.utc)
        }

        if indicators:
            indicator_data = indicators[0]
            # Add all indicator fields to response
            for field in UserIndicatorsResponse.__fields__.keys():
                if field in ["user_id", "updated_at"]:
                    if field == "updated_at" and "updated_at" in indicator_data:
                        response_data[field] = datetime.fromisoformat(indicator_data["updated_at"])
                    continue

                if field in indicator_data:
                    if field == "birth_date" and isinstance(indicator_data[field], str):
                        # Convert ISO string back to date
                        response_data[field] = date.fromisoformat(indicator_data[field])
                    else:
                        response_data[field] = indicator_data[field]

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="user_indicators_retrieved",
            user_id=current_user.id,
            details={
                "has_data": len(indicators) > 0,
                "fields_count": len([f for f in response_data.values() if f is not None])
            },
        )

        return UserIndicatorsResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "User indicators retrieval error",
            user_id=getattr(current_user, 'id', 'unknown'),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user indicators",
        )
