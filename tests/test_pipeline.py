"""
Integration test: runs the full pipeline in mock mode against sample data.
Verifies that the audit log is correctly populated for all invoice scenarios.
"""

import pytest
import os
import sys
import json
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPipelineIntegration:
    """End-to-end pipeline test using mock mode (no API key required)."""

    def setup_method(self):
        # Save original env and ensure mock mode
        self.original_key = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = ""

        # Create a temp CSV
        self.tmp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.tmp_dir, "test_invoices.csv")

        with open(self.csv_path, "w") as f:
            f.write("invoice_no,client_name,amount,due_date,contact_email,follow_up_count,days_overdue\n")
            f.write("INV-T-001,Alice Test,10000,2026-05-10,alice@test.com,0,3\n")     # Stage 1
            f.write("INV-T-002,Bob Test,20000,2026-05-01,bob@test.com,1,12\n")        # Stage 2
            f.write("INV-T-003,Carol Test,30000,2026-04-25,carol@test.com,2,18\n")    # Stage 3
            f.write("INV-T-004,Dave Test,40000,2026-04-18,dave@test.com,3,25\n")      # Stage 4
            f.write("INV-T-005,Eve Test,50000,2026-04-01,eve@test.com,4,42\n")        # Escalated
            f.write("INV-T-006,Frank Test,5000,2026-05-20,frank@test.com,0,-7\n")     # Skipped

    def teardown_method(self):
        # Restore original env
        if self.original_key:
            os.environ["OPENAI_API_KEY"] = self.original_key
        elif "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_full_pipeline_mock_mode(self):
        """Run the full pipeline and verify audit log output."""
        # Change to project directory for template loading
        original_cwd = os.getcwd()
        project_dir = os.path.join(os.path.dirname(__file__), "..")
        os.chdir(project_dir)

        try:
            from src.main import main
            results = main(csv_path=self.csv_path)
        finally:
            os.chdir(original_cwd)

        assert results is not None
        assert len(results) == 6

        # Check status distribution
        statuses = [r["status"] for r in results]
        assert statuses.count("generated") == 4
        assert statuses.count("escalated") == 1
        assert statuses.count("skipped") == 1

        # Check that generated emails have required fields
        for entry in results:
            if entry["status"] == "generated":
                assert "subject" in entry
                assert "body" in entry
                assert "tone" in entry

    def test_audit_json_file_created(self):
        """Verify the JSON audit log file is created."""
        original_cwd = os.getcwd()
        project_dir = os.path.join(os.path.dirname(__file__), "..")
        os.chdir(project_dir)

        try:
            from src.main import main
            main(csv_path=self.csv_path)
        finally:
            os.chdir(original_cwd)

        json_path = os.path.join(project_dir, "logs", "audit_log.json")
        assert os.path.exists(json_path)

        with open(json_path) as f:
            data = json.load(f)
        assert len(data) >= 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])