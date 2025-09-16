"""
Garmin credential management routes (Phase 5).

This module provides REST endpoints for managing encrypted Garmin credentials
according to the migration plan Phase 5: API Service Integration.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
import structlog

from ..models.requests import (
    CreateGarminCredentialsRequest,
    UpdateGarminCredentialsRequest,
)
from ..models.responses import (
    GarminCredentialResponse,
    GarminCredentialTestResponse,
)
from ..middleware.auth import get_current_user
from ..middleware.logging import audit_logger
from ..database import get_db, User
from ..services import GarminCredentialService
from sqlmodel import Session

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/garmin/credentials", tags=["garmin-credentials"])


@router.post("", response_model=GarminCredentialResponse)
async def create_garmin_credentials(
    request: Request,
    credential_request: CreateGarminCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GarminCredentialResponse:
    """
    Create or update Garmin credentials for the current user.

    Creates encrypted Garmin Connect credentials and tests authentication.
    """
    try:
        logger.info(f"Creating Garmin credentials for user {current_user.id}")

        # Initialize credential service
        credential_service = GarminCredentialService(db)

        # Create encrypted credentials (includes authentication test)
        credential_record = credential_service.create_credentials_sync(
            user_id=current_user.id,
            username=credential_request.garmin_username,
            password=credential_request.garmin_password,
        )

        # Test credentials to get status
        test_result = credential_service.test_credentials_sync(current_user.id)

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="garmin_credentials_created",
            user_id=current_user.id,
            details={
                "garmin_username": credential_request.garmin_username,
                "test_status": test_result.get("success", False),
            },
        )

        return GarminCredentialResponse(
            user_id=current_user.id,
            garmin_username=credential_record.garmin_username,
            has_credentials=True,
            created_at=credential_record.created_at,
            updated_at=credential_record.updated_at,
            last_tested=test_result.get("test_timestamp"),
            test_status="success" if test_result.get("success") else "failed",
        )

    except ValueError as ve:
        logger.warning(
            f"Invalid credential creation request for user {current_user.id}: {ve}"
        )
        if "already exist" in str(ve):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Garmin credentials already exist for this user. Use PUT to update.",
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        logger.error(
            f"Failed to create Garmin credentials for user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Garmin credentials",
        )


@router.get("", response_model=GarminCredentialResponse)
async def get_garmin_credentials(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GarminCredentialResponse:
    """
    Get Garmin credential status (without exposing password).

    Returns credential metadata without decrypting sensitive information.
    """
    try:
        logger.debug(f"Getting Garmin credential status for user {current_user.id}")

        # Initialize credential service
        credential_service = GarminCredentialService(db)

        # Get credential info without decrypting password
        credential_info = credential_service.get_credential_info_sync(current_user.id)

        if not credential_info:
            return GarminCredentialResponse(
                user_id=current_user.id,
                garmin_username="",
                has_credentials=False,
                created_at=None,
                updated_at=None,
                last_tested=None,
                test_status=None,
            )

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="garmin_credentials",
            operation="read_status",
            details={"garmin_username": credential_info.garmin_username},
        )

        return GarminCredentialResponse(
            user_id=current_user.id,
            garmin_username=credential_info.garmin_username,
            has_credentials=True,
            created_at=credential_info.created_at,
            updated_at=credential_info.updated_at,
            last_tested=None,  # Would need separate tracking
            test_status=None,  # Would need separate tracking
        )

    except Exception as e:
        logger.error(
            f"Failed to get Garmin credentials for user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Garmin credential status",
        )


@router.put("", response_model=GarminCredentialResponse)
async def update_garmin_credentials(
    request: Request,
    update_request: UpdateGarminCredentialsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GarminCredentialResponse:
    """
    Update existing Garmin credentials.

    Updates username and/or password for existing Garmin credentials.
    """
    try:
        logger.info(f"Updating Garmin credentials for user {current_user.id}")

        # Validate that at least one field is provided
        if not update_request.garmin_username and not update_request.garmin_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either garmin_username or garmin_password to update",
            )

        # Initialize credential service
        credential_service = GarminCredentialService(db)

        # Update credentials
        credential_record = credential_service.update_credentials_sync(
            user_id=current_user.id,
            username=update_request.garmin_username,
            password=update_request.garmin_password,
        )

        if not credential_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Garmin credentials found for this user",
            )

        # Test updated credentials if password was changed
        test_result = None
        if update_request.garmin_password:
            test_result = credential_service.test_credentials_sync(current_user.id)

        # Log user action
        update_fields = []
        if update_request.garmin_username:
            update_fields.append("username")
        if update_request.garmin_password:
            update_fields.append("password")

        audit_logger.log_user_action(
            request=request,
            action="garmin_credentials_updated",
            user_id=current_user.id,
            details={
                "updated_fields": update_fields,
                "test_status": test_result.get("success") if test_result else None,
            },
        )

        return GarminCredentialResponse(
            user_id=current_user.id,
            garmin_username=credential_record.garmin_username,
            has_credentials=True,
            created_at=credential_record.created_at,
            updated_at=credential_record.updated_at,
            last_tested=test_result.get("test_timestamp") if test_result else None,
            test_status=(
                "success" if test_result and test_result.get("success") else "failed"
            ),
        )

    except ValueError as ve:
        logger.warning(
            f"Invalid credential update request for user {current_user.id}: {ve}"
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update Garmin credentials for user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Garmin credentials",
        )


@router.delete("")
async def delete_garmin_credentials(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Delete Garmin credentials for the current user.

    Permanently removes encrypted Garmin credentials from the database.
    """
    try:
        logger.info(f"Deleting Garmin credentials for user {current_user.id}")

        # Initialize credential service
        credential_service = GarminCredentialService(db)

        # Delete credentials
        deleted = credential_service.delete_credentials_sync(current_user.id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Garmin credentials found for this user",
            )

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="garmin_credentials_deleted",
            user_id=current_user.id,
            details={},
        )

        return {"success": True, "message": "Garmin credentials deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete Garmin credentials for user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete Garmin credentials",
        )


@router.post("/test", response_model=GarminCredentialTestResponse)
async def test_garmin_credentials(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GarminCredentialTestResponse:
    """
    Test Garmin credentials authentication.

    Verifies that stored credentials can successfully authenticate with Garmin Connect.
    """
    try:
        logger.info(f"Testing Garmin credentials for user {current_user.id}")

        # Initialize credential service
        credential_service = GarminCredentialService(db)

        # Test credentials
        test_result = credential_service.test_credentials_sync(current_user.id)

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="garmin_credentials_tested",
            user_id=current_user.id,
            details={
                "test_success": test_result.get("success", False),
                "test_message": test_result.get("message", "Unknown"),
            },
        )

        return GarminCredentialTestResponse(
            success=test_result.get("success", False),
            message=test_result.get("message", "Test completed"),
            test_timestamp=test_result.get(
                "test_timestamp", datetime.now(timezone.utc)
            ),
            error_details=test_result.get("error_details"),
        )

    except Exception as e:
        logger.error(
            f"Failed to test Garmin credentials for user {current_user.id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to test Garmin credentials",
        )
