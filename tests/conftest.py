"""Root test configuration — shared across all test layers.

Unit-specific mocks live in tests/unit/conftest.py.
Integration-specific setup lives in tests/integration/conftest.py.

This file is intentionally minimal so that integration tests
can import real project modules without stub interference.
"""
