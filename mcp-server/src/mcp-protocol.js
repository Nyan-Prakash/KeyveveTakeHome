/**
 * MCP Protocol implementation for tool registration and execution
 */
export class MCPProtocol {
  constructor() {
    this.tools = new Map();
  }

  /**
   * Register a tool with the MCP server
   */
  registerTool(name, tool) {
    if (!tool.getMetadata || typeof tool.getMetadata !== 'function') {
      throw new Error('Tool must implement getMetadata() method');
    }
    
    if (!tool.call || typeof tool.call !== 'function') {
      throw new Error('Tool must implement call() method');
    }

    this.tools.set(name, tool);
    console.log(`🔧 Registered MCP tool: ${name}`);
  }

  /**
   * List all registered tools
   */
  listTools() {
    return Array.from(this.tools.entries()).map(([name, tool]) => ({
      name,
      ...tool.getMetadata()
    }));
  }

  /**
   * Call a registered tool
   */
  async callTool(name, args) {
    const tool = this.tools.get(name);
    
    if (!tool) {
      throw new Error(`Tool '${name}' not found. Available tools: ${Array.from(this.tools.keys()).join(', ')}`);
    }

    try {
      // Validate arguments against schema if available
      const metadata = tool.getMetadata();
      if (metadata.inputSchema) {
        this._validateArgs(args, metadata.inputSchema);
      }

      // Call the tool
      const result = await tool.call(args);
      
      return result;
    } catch (error) {
      throw new Error(`Tool execution failed: ${error.message}`);
    }
  }

  /**
   * Basic argument validation against JSON schema
   */
  _validateArgs(args, schema) {
    if (schema.required) {
      for (const required of schema.required) {
        if (!(required in args)) {
          throw new Error(`Missing required argument: ${required}`);
        }
      }
    }

    if (schema.properties) {
      for (const [key, value] of Object.entries(args)) {
        const propSchema = schema.properties[key];
        if (propSchema) {
          this._validateProperty(value, propSchema, key);
        }
      }
    }
  }

  /**
   * Validate individual property
   */
  _validateProperty(value, schema, propName) {
    if (schema.type) {
      const actualType = Array.isArray(value) ? 'array' : typeof value;
      
      if (schema.type === 'integer' && actualType === 'number') {
        if (!Number.isInteger(value)) {
          throw new Error(`Property ${propName} must be an integer`);
        }
      } else if (actualType !== schema.type) {
        throw new Error(`Property ${propName} must be of type ${schema.type}, got ${actualType}`);
      }
    }

    if (schema.minimum !== undefined && value < schema.minimum) {
      throw new Error(`Property ${propName} must be >= ${schema.minimum}`);
    }

    if (schema.maximum !== undefined && value > schema.maximum) {
      throw new Error(`Property ${propName} must be <= ${schema.maximum}`);
    }
  }
}
