"""MCP protocol exceptions."""


class MCPException(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPConnectionError(MCPException):
    """Raised when unable to connect to MCP server."""
    pass


class MCPTimeoutError(MCPException):
    """Raised when MCP server request times out."""
    pass


class MCPToolNotFoundError(MCPException):
    """Raised when requested tool is not available on MCP server."""
    pass


class MCPValidationError(MCPException):
    """Raised when tool arguments fail validation."""
    pass
