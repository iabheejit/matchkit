"""Tests for utils/csv_loader.py."""
import pytest
import tempfile
import csv
from pathlib import Path

from utils.csv_loader import load_organizations_from_csv, _parse_comma_list, _parse_size, _safe_str


class TestParseHelpers:
    def test_parse_comma_list(self):
        assert _parse_comma_list("Technology, Education, Finance") == [
            "Technology", "Education", "Finance"
        ]
        assert _parse_comma_list("") == []
        assert _parse_comma_list(None) == []
        assert _parse_comma_list("Single") == ["Single"]

    def test_parse_size_from_number(self):
        assert _parse_size("5") == "Small"
        assert _parse_size("50") == "Medium"
        assert _parse_size("200") == "Large"

    def test_parse_size_from_name(self):
        assert _parse_size("small") == "Small"
        assert _parse_size("Large") == "Large"

    def test_parse_size_default(self):
        assert _parse_size(None) == "Medium"
        assert _parse_size("") == "Medium"

    def test_safe_str(self):
        assert _safe_str("hello") == "hello"
        assert _safe_str(None) is None
        assert _safe_str("") is None
        assert _safe_str(float("nan")) is None


class TestLoadOrganizations:
    def _create_csv(self, rows: list[dict]) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
        fieldnames = rows[0].keys() if rows else ["organization_name"]
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        tmp.close()
        return Path(tmp.name)

    def test_load_basic_org(self):
        csv_path = self._create_csv([
            {
                "organization_name": "Test Org",
                "description": "A test organization",
                "website": "https://test.org",
                "city": "San Francisco",
                "state": "California",
                "regions": "California, Oregon",
                "interests": "Technology, Education",
                "preferences": "Youth, Students",
                "num_employees": "50",
                "email": "test@test.org",
                "key_people": "Jane Doe",
                "activities": "Training",
                "linkedin": "",
                "twitter": "",
                "facebook": "",
                "metadata": "",
                "year_established": "2010",
                "org_type": "Nonprofit",
                "external_id": "EXT123",
                "phone": "",
            }
        ])
        orgs = load_organizations_from_csv(csv_path)
        assert len(orgs) == 1
        org = orgs[0]
        assert org.name == "Test Org"
        assert org.interests == ["Technology", "Education"]
        assert org.regions == ["California", "Oregon"]
        assert org.organization_size == "Medium"
        assert org.contact_email == "test@test.org"

    def test_deduplicates_by_name(self):
        csv_path = self._create_csv([
            {"organization_name": "Dup Org", "description": "First"},
            {"organization_name": "Dup Org", "description": "Second"},
        ])
        orgs = load_organizations_from_csv(csv_path)
        assert len(orgs) == 1

    def test_skips_empty_names(self):
        csv_path = self._create_csv([
            {"organization_name": "", "description": "No name"},
            {"organization_name": "Valid Org", "description": "Has name"},
        ])
        orgs = load_organizations_from_csv(csv_path)
        assert len(orgs) == 1
        assert orgs[0].name == "Valid Org"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_organizations_from_csv("/nonexistent/path.csv")
