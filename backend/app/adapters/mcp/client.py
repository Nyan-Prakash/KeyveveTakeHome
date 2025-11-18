"""MCP client for communicating with MCP servers."""

import asyncio
import logging
from typing import Any, TYPE_CHECKING

try:
    import httpx
except ImportError:  # pragma: no cover - optional dependency for tests
    httpx = None

if TYPE_CHECKING:  # pragma: no cover
    from httpx import AsyncClient  # type: ignore

from .exceptions import MCPConnectionError, MCPException, MCPTimeoutError

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for communicating with MCP (Model Context Protocol) servers."""

    def __init__(self, base_url: str, timeout: float = 5.0):
        """Initialize MCP client.
        
        Args:
            base_url: Base URL of MCP server (e.g., "http://localhost:3001")
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client: Any | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        if httpx is None:
            raise MCPConnectionError("httpx is required for MCP client operations")
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def _get_client(self) -> Any:
        """Get HTTP client, creating if needed."""
        if httpx is None:
            raise MCPConnectionError("httpx is required for MCP client operations")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def health_check(self) -> bool:
        """Check if MCP server is healthy.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"MCP health check failed: {e}")
            return False

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools on MCP server.
        
        Returns:
            List of tool metadata dictionaries
            
        Raises:
            MCPConnectionError: If unable to connect to server
            MCPTimeoutError: If request times out
            MCPException: For other MCP errors
        """
        try:
            client = await self._get_client()
            response = await client.post(f"{self.base_url}/mcp/tools/list")
            response.raise_for_status()
            
            data = response.json()
            return data.get("tools", [])
            
        except httpx.TimeoutException as e:
            raise MCPTimeoutError(f"MCP server request timed out: {e}")
        except httpx.ConnectError as e:
            raise MCPConnectionError(f"Unable to connect to MCP server: {e}")
        except httpx.HTTPStatusError as e:
            raise MCPException(f"MCP server returned error {e.response.status_code}: {e.response.text}")
        except Exception as e:
            raise MCPException(f"Unexpected MCP error: {e}")

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool on the MCP server.
        
        Args:
            tool_name: Name of tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPConnectionError: If unable to connect to server
            MCPTimeoutError: If request times out  
            MCPException: For other MCP errors
        """
        try:
            client = await self._get_client()
            payload = {
                "tool": tool_name,
                "arguments": arguments
            }
            
            response = await client.post(f"{self.base_url}/mcp/tools/call", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                raise MCPException(f"Tool execution failed: {data['error']}")
                
            return data.get("result", {})
            
        except httpx.TimeoutException as e:
            raise MCPTimeoutError(f"MCP tool call timed out: {e}")
        except httpx.ConnectError as e:
            raise MCPConnectionError(f"Unable to connect to MCP server: {e}")
        except httpx.HTTPStatusError as e:
            error_text = e.response.text if hasattr(e.response, 'text') else str(e)
            raise MCPException(f"MCP server returned error {e.response.status_code}: {error_text}")
        except MCPException:
            raise  # Re-raise MCP exceptions as-is
        except Exception as e:
            raise MCPException(f"Unexpected MCP error: {e}")

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
