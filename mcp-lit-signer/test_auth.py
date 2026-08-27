#!/usr/bin/env python3
"""Regression tests for MCP transport authentication and safe bind defaults."""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from starlette.testclient import TestClient

SERVER_PATH = Path(__file__).with_name("server.py")
TEST_API_KEY = "test-only-mcp-bearer-token"


def load_server_module():
    """Load server.py with deterministic test configuration."""
    module_name = "mcp_lit_signer_server_test"
    sys.modules.pop(module_name, None)

    with patch.dict(
        os.environ,
        {
            "MCP_API_KEY": TEST_API_KEY,
            "MCP_HOST": "127.0.0.1",
        },
        clear=False,
    ):
        spec = importlib.util.spec_from_file_location(module_name, SERVER_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


class AuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_server_module()
        cls.initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "auth-regression-test", "version": "1"},
            },
        }
        cls.base_headers = {"Accept": "application/json, text/event-stream"}

    def request(self, authorization=None, payload=None):
        headers = dict(self.base_headers)
        if authorization is not None:
            headers["Authorization"] = authorization
        app = self.server.mcp.http_app(stateless_http=True, json_response=True)
        with TestClient(app) as client:
            return client.post(
                "/mcp",
                headers=headers,
                json=payload or self.initialize_request,
            )

    def rpc_request(self, method, params=None):
        return {
            "jsonrpc": "2.0",
            "id": 2,
            "method": method,
            "params": params or {},
        }

    def test_missing_bearer_token_is_rejected(self):
        response = self.request()
        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_token_is_rejected(self):
        response = self.request("Bearer incorrect-token")
        self.assertEqual(response.status_code, 401)

    def test_valid_bearer_token_is_accepted(self):
        response = self.request(f"Bearer {TEST_API_KEY}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("result", response.json())

    def test_tool_discovery_requires_bearer_token(self):
        payload = self.rpc_request("tools/list")
        self.assertEqual(self.request(payload=payload).status_code, 401)
        response = self.request(f"Bearer {TEST_API_KEY}", payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("tools", response.json()["result"])

    def test_tool_calls_require_bearer_token(self):
        payload = self.rpc_request(
            "tools/call",
            {"name": "not-a-real-tool", "arguments": {}},
        )
        self.assertEqual(self.request(payload=payload).status_code, 401)
        response = self.request(f"Bearer {TEST_API_KEY}", payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["result"]["isError"])

    def test_missing_server_key_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "MCP_API_KEY is required"):
            self.server.build_auth_provider(None)

    def test_default_host_is_loopback(self):
        self.assertEqual(self.server.MCP_HOST, "127.0.0.1")

    def test_flat_deployment_env_beside_server_takes_precedence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            server_directory = root / "mcp-lit-signer"
            server_directory.mkdir()
            server_path = server_directory / "server.py"
            local_env = server_directory / ".env"
            repository_env = root / ".env"
            server_path.touch()
            local_env.touch()
            repository_env.touch()

            self.assertEqual(self.server.resolve_env_path(server_path), local_env)

    def test_repository_root_env_is_fallback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            server_directory = root / "mcp-lit-signer"
            server_directory.mkdir()
            server_path = server_directory / "server.py"
            repository_env = root / ".env"
            server_path.touch()
            repository_env.touch()

            self.assertEqual(self.server.resolve_env_path(server_path), repository_env)

    def test_missing_env_returns_flat_deployment_candidate(self):
        with TemporaryDirectory() as directory:
            server_path = Path(directory) / "server.py"
            expected = server_path.parent / ".env"

            self.assertEqual(self.server.resolve_env_path(server_path), expected)

    def test_stdio_does_not_receive_http_bind_arguments(self):
        with patch.object(self.server.mcp, "run") as run:
            self.server.run_server("stdio")
            run.assert_called_once_with(transport="stdio")

    def test_api_key_is_not_in_tool_schema(self):
        async def assert_schemas():
            tools = await self.server.mcp.list_tools()
            signing_tools = {
                tool.name: tool
                for tool in tools
                if tool.name in {"anchor_state_via_pkp", "anchor_action_via_pkp"}
            }
            self.assertEqual(len(signing_tools), 2)
            for tool in signing_tools.values():
                properties = tool.parameters.get("properties", {})
                self.assertNotIn("api_key", properties)

        import asyncio

        asyncio.run(assert_schemas())


if __name__ == "__main__":
    unittest.main()
