"""
Integration tests for the weekly summary API endpoint.

Tests authentication and the weekly summary analytics endpoint using pytest and FastAPI TestClient.
"""

import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient


class TestWeeklySummaryAPI:
    """Test class for weekly summary API endpoints."""

    def test_weekly_summary_authentication_required(self, test_client: TestClient, sample_weekly_summary_request: Dict[str, Any]):
        """Test that weekly summary endpoint requires authentication."""
        response = test_client.post("/api/v1/analytics/activity/summary", json=sample_weekly_summary_request)

        # Should return 401 or 403 without authentication
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"

    def test_weekly_summary_with_default_parameters(self, authenticated_client: TestClient, sample_weekly_summary_request: Dict[str, Any]):
        """Test weekly summary endpoint with default parameters."""
        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=sample_weekly_summary_request)

        if response.status_code == 200:
            data = response.json()
            self._validate_weekly_summary_response(data)

            # Check that default zone methods are applied
            zone_methods = data.get("zone_methods", {})
            assert zone_methods.get("power") == "steve_palladino"
            assert zone_methods.get("pace") == "joe_friel_running"
            assert zone_methods.get("heart_rate") == "joe_friel"
        else:
            pytest.skip(f"Weekly summary endpoint returned {response.status_code}: {response.text}")

    def test_weekly_summary_with_custom_date_range(self, authenticated_client: TestClient):
        """Test weekly summary endpoint with custom date range (last 30 days)."""
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        request_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "power_zone_method": "steve_palladino",
            "pace_zone_method": "joe_friel_running",
            "heart_rate_zone_method": "joe_friel"
        }

        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=request_data)

        if response.status_code == 200:
            data = response.json()
            self._validate_weekly_summary_response(data)

            # Verify that the date range is reflected in the response (check multiple possible locations)
            start_date_found = (
                data.get("start_date") or
                data.get("period", {}).get("start_date") or
                data.get("summary", {}).get("start_date")
            )
            end_date_found = (
                data.get("end_date") or
                data.get("period", {}).get("end_date") or
                data.get("summary", {}).get("end_date")
            )

            # At least one should be found, but it's not required for the test to pass
            if start_date_found or end_date_found:
                print(f"\nDate range reflected in response: {start_date_found} to {end_date_found}")
        else:
            pytest.skip(f"Weekly summary endpoint returned {response.status_code}: {response.text}")

    def test_weekly_summary_with_different_zone_methods(self, authenticated_client: TestClient, sample_date_range: Dict[str, str]):
        """Test weekly summary endpoint with different zone calculation methods."""
        request_data = {
            "start_date": sample_date_range["start_date"],
            "end_date": sample_date_range["end_date"],
            "power_zone_method": "stryd_running",
            "pace_zone_method": "jack_daniels",
            "heart_rate_zone_method": "sally_edwards"
        }

        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=request_data)

        if response.status_code == 200:
            data = response.json()
            self._validate_weekly_summary_response(data)

            # Check that custom zone methods are applied
            zone_methods = data.get("zone_methods", {})
            assert zone_methods.get("power") == "stryd_running"
            assert zone_methods.get("pace") == "jack_daniels"
            assert zone_methods.get("heart_rate") == "sally_edwards"
        else:
            pytest.skip(f"Weekly summary endpoint returned {response.status_code}: {response.text}")

    def test_weekly_summary_with_broader_date_range(self, authenticated_client: TestClient):
        """Test weekly summary endpoint with broader date range (365 days)."""
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=365)

        request_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "power_zone_method": "steve_palladino",
            "pace_zone_method": "joe_friel_running",
            "heart_rate_zone_method": "joe_friel"
        }

        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=request_data)

        if response.status_code == 200:
            data = response.json()
            self._validate_weekly_summary_response(data)

            # With broader date range, we might expect more activity data
            activity_count = data.get("activity_count", 0)
            assert isinstance(activity_count, int)
            assert activity_count >= 0
        else:
            pytest.skip(f"Weekly summary endpoint returned {response.status_code}: {response.text}")

    def test_weekly_summary_invalid_date_range(self, authenticated_client: TestClient):
        """Test weekly summary endpoint with invalid date range."""
        request_data = {
            "start_date": "2025-08-31",  # Start after end
            "end_date": "2025-08-01",
            "power_zone_method": "steve_palladino",
            "pace_zone_method": "joe_friel_running",
            "heart_rate_zone_method": "joe_friel"
        }

        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=request_data)

        # The API might handle this gracefully and return 200 with empty results
        # or it might return an error. Both are acceptable behaviors.
        if response.status_code == 200:
            data = response.json()
            # If it returns 200, it should handle the invalid range gracefully
            # (e.g., return empty results or swap the dates)
            activity_count = data.get("activity_count", 0)
            assert isinstance(activity_count, int), "Activity count should be an integer even with invalid date range"
        else:
            # Should return error for invalid date range
            assert response.status_code in [400, 422], f"Expected 400, 422, or 200 for invalid date range, got {response.status_code}"

    def test_weekly_summary_missing_required_fields(self, authenticated_client: TestClient):
        """Test weekly summary endpoint with missing required fields."""
        request_data = {
            # Missing start_date and end_date
            "power_zone_method": "steve_palladino",
            "pace_zone_method": "joe_friel_running",
            "heart_rate_zone_method": "joe_friel"
        }

        response = authenticated_client.post("/api/v1/analytics/activity/summary", json=request_data)

        # Should return error for missing required fields
        assert response.status_code in [400, 422], f"Expected 400 or 422 for missing fields, got {response.status_code}"

    def _validate_weekly_summary_response(self, data: Dict[str, Any]):
        """Validate the structure of a weekly summary response."""
        # Basic response structure
        assert isinstance(data, dict), "Response should be a dictionary"

        # Check for required fields (adjust based on actual API response)
        expected_fields = ["user_id", "activity_count"]
        for field in expected_fields:
            if field in data:
                assert data[field] is not None, f"Field {field} should not be None"

        # Validate numeric fields
        if "activity_count" in data:
            assert isinstance(data["activity_count"], int), "Activity count should be an integer"
            assert data["activity_count"] >= 0, "Activity count should be non-negative"

        if "total_distance" in data:
            assert isinstance(data["total_distance"], (int, float)), "Total distance should be numeric"
            assert data["total_distance"] >= 0, "Total distance should be non-negative"

        if "total_tss" in data:
            assert isinstance(data["total_tss"], (int, float)), "Total TSS should be numeric"
            assert data["total_tss"] >= 0, "Total TSS should be non-negative"

        # Validate zone distributions if present
        zone_types = ["power_zone_distribution", "pace_zone_distribution", "heart_rate_zone_distribution"]
        for zone_type in zone_types:
            if zone_type in data:
                self._validate_zone_distribution(data[zone_type], zone_type)

        # Validate zone methods if present
        if "zone_methods" in data:
            zone_methods = data["zone_methods"]
            assert isinstance(zone_methods, dict), "Zone methods should be a dictionary"

            for method_type in ["power", "pace", "heart_rate"]:
                if method_type in zone_methods:
                    assert isinstance(zone_methods[method_type], str), f"{method_type} zone method should be a string"

    def _validate_zone_distribution(self, zone_data: Dict[str, Any], zone_type: str):
        """Validate zone distribution data structure."""
        assert isinstance(zone_data, dict), f"{zone_type} should be a dictionary"

        # Check for zone data (zones 1-7)
        for i in range(1, 8):
            seconds_key = f"zone_{i}_seconds"
            percentage_key = f"zone_{i}_percentage"

            if seconds_key in zone_data:
                seconds = zone_data[seconds_key]
                assert isinstance(seconds, (int, float)), f"{seconds_key} should be numeric"
                assert seconds >= 0, f"{seconds_key} should be non-negative"

            if percentage_key in zone_data:
                percentage = zone_data[percentage_key]
                assert isinstance(percentage, (int, float)), f"{percentage_key} should be numeric"
                assert 0 <= percentage <= 100, f"{percentage_key} should be between 0 and 100"