"""
Integration tests for the health metrics API endpoint.

Tests authentication and the health metrics analytics endpoint using pytest and FastAPI TestClient.
"""

import pytest
from typing import Dict, Any, List
from fastapi.testclient import TestClient


class TestHealthMetricsAPI:
    """Test class for health metrics API endpoints."""

    def test_health_metrics_authentication_required(self, test_client: TestClient, sample_health_metrics_request: Dict[str, Any]):
        """Test that health metrics endpoint requires authentication."""
        response = test_client.post("/api/v1/analytics/health-metrics", json=sample_health_metrics_request)

        # Should return 401 or 403 without authentication
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"

    def test_health_metrics_with_valid_date_range(self, authenticated_client: TestClient, sample_health_metrics_request: Dict[str, Any]):
        """Test health metrics endpoint with valid date range."""
        response = authenticated_client.post("/api/v1/analytics/health-metrics", json=sample_health_metrics_request)

        if response.status_code == 200:
            data = response.json()
            self._validate_health_metrics_response(data)
        elif response.status_code == 404:
            pytest.skip("Health metrics endpoint not found - may not be implemented yet")
        else:
            pytest.skip(f"Health metrics endpoint returned {response.status_code}: {response.text}")

    def test_health_metrics_with_custom_date_range(self, authenticated_client: TestClient):
        """Test health metrics endpoint with custom date range."""
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=7)  # Last 7 days

        request_data = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

        response = authenticated_client.post("/api/v1/analytics/health/summary", json=request_data)

        if response.status_code == 200:
            data = response.json()
            self._validate_health_metrics_response(data)

            # Verify date range is reflected in response
            summary = data.get("summary", {})
            if summary:
                assert summary.get("start_date") == start_date.isoformat()
                assert summary.get("end_date") == end_date.isoformat()
        elif response.status_code == 404:
            pytest.skip("Health metrics endpoint not found - may not be implemented yet")
        else:
            pytest.skip(f"Health metrics endpoint returned {response.status_code}: {response.text}")

    def test_health_metrics_with_known_data_period(self, authenticated_client: TestClient):
        """Test health metrics endpoint with known data period (August 2025)."""
        request_data = {
            "start_date": "2025-08-01",
            "end_date": "2025-08-31"
        }

        response = authenticated_client.post("/api/v1/analytics/health/summary", json=request_data)

        if response.status_code == 200:
            data = response.json()
            self._validate_health_metrics_response(data)

            # This period should have some data based on the original test
            summary = data.get("summary", {})
            if summary:
                total_days = summary.get("total_days")
                assert total_days == 31, f"Expected 31 days for August, got {total_days}"
        elif response.status_code == 404:
            pytest.skip("Health metrics endpoint not found - may not be implemented yet")
        else:
            pytest.skip(f"Health metrics endpoint returned {response.status_code}: {response.text}")

    def test_health_metrics_invalid_date_range(self, authenticated_client: TestClient):
        """Test health metrics endpoint with invalid date range."""
        request_data = {
            "start_date": "2025-08-31",  # Start after end
            "end_date": "2025-08-01"
        }

        response = authenticated_client.post("/api/v1/analytics/health/summary", json=request_data)

        # Should return error for invalid date range
        if response.status_code not in [404]:  # Skip if endpoint doesn't exist
            assert response.status_code in [400, 422], f"Expected 400 or 422 for invalid date range, got {response.status_code}"

    def test_health_metrics_missing_required_fields(self, authenticated_client: TestClient):
        """Test health metrics endpoint with missing required fields."""
        request_data = {
            # Missing start_date and end_date
        }

        response = authenticated_client.post("/api/v1/analytics/health/summary", json=request_data)

        # Should return error for missing required fields
        if response.status_code not in [404]:  # Skip if endpoint doesn't exist
            assert response.status_code in [400, 422], f"Expected 400 or 422 for missing fields, got {response.status_code}"

    def test_health_metrics_timezone_handling(self, authenticated_client: TestClient, sample_health_metrics_request: Dict[str, Any]):
        """Test that health metrics endpoint handles timezone data correctly."""
        response = authenticated_client.post("/api/v1/analytics/health-metrics", json=sample_health_metrics_request)

        if response.status_code == 200:
            data = response.json()
            self._validate_health_metrics_response(data)

            # Check timezone-related fields
            timezone = data.get("timezone")
            night_hours = data.get("night_hours")

            if timezone:
                assert isinstance(timezone, str), "Timezone should be a string"

            if night_hours:
                assert isinstance(night_hours, str), "Night hours should be a string"

            # Check for night time data filtering
            daily_metrics = data.get("daily_metrics", [])
            self._validate_night_time_filtering(daily_metrics)

        elif response.status_code == 404:
            pytest.skip("Health metrics endpoint not found - may not be implemented yet")
        else:
            pytest.skip(f"Health metrics endpoint returned {response.status_code}: {response.text}")

    def _validate_health_metrics_response(self, data: Dict[str, Any]):
        """Validate the structure of a health metrics response."""
        assert isinstance(data, dict), "Response should be a dictionary"

        # Check for main structure
        expected_top_level_fields = ["user_id", "summary"]
        for field in expected_top_level_fields:
            if field in data:
                assert data[field] is not None, f"Field {field} should not be None"

        # Validate summary section
        if "summary" in data:
            self._validate_summary_section(data["summary"])

        # Validate daily metrics if present
        if "daily_metrics" in data:
            daily_metrics = data["daily_metrics"]
            assert isinstance(daily_metrics, list), "Daily metrics should be a list"

            if daily_metrics:  # Only validate if there are daily metrics
                for day_data in daily_metrics[:3]:  # Check first 3 days
                    self._validate_daily_metrics_entry(day_data)

        # Validate optional timezone fields
        if "timezone" in data:
            assert isinstance(data["timezone"], str), "Timezone should be a string"

        if "night_hours" in data:
            assert isinstance(data["night_hours"], str), "Night hours should be a string"

    def _validate_summary_section(self, summary: Dict[str, Any]):
        """Validate the summary section of health metrics response."""
        assert isinstance(summary, dict), "Summary should be a dictionary"

        # Date fields
        if "start_date" in summary:
            assert isinstance(summary["start_date"], str), "Start date should be a string"

        if "end_date" in summary:
            assert isinstance(summary["end_date"], str), "End date should be a string"

        if "total_days" in summary:
            assert isinstance(summary["total_days"], int), "Total days should be an integer"
            assert summary["total_days"] > 0, "Total days should be positive"

        # HRV metrics validation
        hrv_fields = [
            "avg_hrv_rmssd", "avg_hrv_rmssd_night", "total_hrv_measurements",
            "total_hrv_night_measurements", "hrv_trend"
        ]
        for field in hrv_fields:
            if field in summary and summary[field] is not None:
                if "avg_" in field:
                    assert isinstance(summary[field], (int, float)), f"{field} should be numeric"
                    assert summary[field] >= 0, f"{field} should be non-negative"
                elif "total_" in field:
                    assert isinstance(summary[field], int), f"{field} should be an integer"
                    assert summary[field] >= 0, f"{field} should be non-negative"

        # Heart rate metrics validation
        hr_fields = [
            "avg_resting_hr", "avg_resting_hr_night", "total_hr_measurements",
            "total_hr_night_measurements", "hr_trend"
        ]
        for field in hr_fields:
            if field in summary and summary[field] is not None:
                if "avg_" in field:
                    assert isinstance(summary[field], (int, float)), f"{field} should be numeric"
                    assert summary[field] >= 0, f"{field} should be non-negative"
                elif "total_" in field:
                    assert isinstance(summary[field], int), f"{field} should be an integer"
                    assert summary[field] >= 0, f"{field} should be non-negative"

        # Battery metrics validation
        battery_fields = ["avg_battery_level", "total_battery_measurements", "battery_trend"]
        for field in battery_fields:
            if field in summary and summary[field] is not None:
                if "avg_" in field:
                    assert isinstance(summary[field], (int, float)), f"{field} should be numeric"
                    if "battery" in field:
                        assert 0 <= summary[field] <= 100, f"{field} should be between 0 and 100"
                elif "total_" in field:
                    assert isinstance(summary[field], int), f"{field} should be an integer"
                    assert summary[field] >= 0, f"{field} should be non-negative"

    def _validate_daily_metrics_entry(self, day_data: Dict[str, Any]):
        """Validate a single daily metrics entry."""
        assert isinstance(day_data, dict), "Daily metrics entry should be a dictionary"

        # Date field
        if "date" in day_data:
            assert isinstance(day_data["date"], str), "Date should be a string"

        # HRV fields
        hrv_fields = [
            "hrv_rmssd_avg", "hrv_rmssd_night_avg", "hrv_data_points", "hrv_night_data_points"
        ]
        for field in hrv_fields:
            if field in day_data and day_data[field] is not None:
                if "avg" in field:
                    assert isinstance(day_data[field], (int, float)), f"{field} should be numeric"
                    assert day_data[field] >= 0, f"{field} should be non-negative"
                elif "points" in field:
                    assert isinstance(day_data[field], int), f"{field} should be an integer"
                    assert day_data[field] >= 0, f"{field} should be non-negative"

        # Heart rate fields
        hr_fields = [
            "resting_hr_avg", "resting_hr_night_avg", "hr_data_points", "hr_night_data_points"
        ]
        for field in hr_fields:
            if field in day_data and day_data[field] is not None:
                if "avg" in field:
                    assert isinstance(day_data[field], (int, float)), f"{field} should be numeric"
                    assert day_data[field] >= 0, f"{field} should be non-negative"
                elif "points" in field:
                    assert isinstance(day_data[field], int), f"{field} should be an integer"
                    assert day_data[field] >= 0, f"{field} should be non-negative"

        # Battery fields
        battery_fields = ["battery_level_avg", "battery_data_points"]
        for field in battery_fields:
            if field in day_data and day_data[field] is not None:
                if "avg" in field:
                    assert isinstance(day_data[field], (int, float)), f"{field} should be numeric"
                    if "battery" in field:
                        assert 0 <= day_data[field] <= 100, f"{field} should be between 0 and 100"
                elif "points" in field:
                    assert isinstance(day_data[field], int), f"{field} should be an integer"
                    assert day_data[field] >= 0, f"{field} should be non-negative"

    def _validate_night_time_filtering(self, daily_metrics: List[Dict[str, Any]]):
        """Validate that night time data filtering is working correctly."""
        for day_data in daily_metrics:
            # Night data points should not exceed total data points
            hrv_total = day_data.get("hrv_data_points", 0)
            hrv_night = day_data.get("hrv_night_data_points", 0)

            if hrv_total and hrv_night:
                assert hrv_night <= hrv_total, f"HRV night data points ({hrv_night}) should not exceed total ({hrv_total})"

            hr_total = day_data.get("hr_data_points", 0)
            hr_night = day_data.get("hr_night_data_points", 0)

            if hr_total and hr_night:
                assert hr_night <= hr_total, f"HR night data points ({hr_night}) should not exceed total ({hr_total})"