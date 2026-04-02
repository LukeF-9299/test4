# File-Based Server Configuration Guide

The Lite LLM API Service uses a **file-based configuration** for servers and models instead of a database table. This makes it easy to manage your model servers and switch between local and production databases.

## Configuration File Structure

The `servers_config.json` file contains all your server configurations:

```json
{
  "servers": [
    {
      "name": "Your Custom Server",
      "endpoint": "http://localhost:8080",
      "models": ["your-model-name"],
      "weight": 1,
      "api_key_required": false,
      "adapter_type": "openai",
      "description": "Your custom model server"
    }
  ],
  "load_balancing": {
    "strategy": "weighted",
    "health_check_interval": 30,
    "retry_attempts": 3
  },
  "api_keys": {
    "openai": "your-openai-api-key-here"
  }
}
```

## Server Configuration Options

### Server Fields
- **name**: Unique server name (used for identification)
- **endpoint**: Base URL of the model server
- **models**: Array of available model names
- **weight**: Load balancing weight (higher = more traffic)
- **api_key_required**: Whether the server requires authentication
- **adapter_type**: API adapter type (see below)
- **description**: Optional description of the server

### Adapter Types

#### **OpenAI-Compatible (`"openai"`)**
For servers that follow the OpenAI API format:
```json
{
  "name": "OpenAI Compatible Server",
  "endpoint": "http://localhost:8080",
  "models": ["gpt-3.5-turbo", "custom-model"],
  "weight": 1,
  "api_key_required": false,
  "adapter_type": "openai"
}
```

#### **Custom API (`"custom"`)**
For servers with non-OpenAI API formats:
```json
{
  "name": "Custom API Server",
  "endpoint": "http://localhost:9000",
  "models": ["custom-embedding-v1"],
  "weight": 1,
  "api_key_required": false,
  "adapter_type": "custom",
  "endpoints": {
    "completion": "/generate",
    "embedding": "/embed"
  },
  "request_format": "custom",
  "response_format": "openai"
}
```

#### **Hugging Face Format (`"huggingface"`)**
For servers using Hugging Face API format:
```json
{
  "name": "Hugging Face Compatible Server",
  "endpoint": "http://localhost:8083",
  "models": ["mistral-7b", "llama-2-7b"],
  "weight": 2,
  "api_key_required": false,
  "adapter_type": "huggingface"
}
```

### Load Balancing Options
- **strategy**: "weighted", "round_robin", "least_busy", "health_check_based"
- **health_check_interval**: Seconds between health checks
- **retry_attempts**: Number of retry attempts for failed requests

### API Keys Configuration
Store your API keys for different providers:
- **openai**: OpenAI API key (if using OpenAI servers)

## Database Configuration

### Local Development (SQLite)
```env
ENVIRONMENT=development
USE_LOCAL_DB=true
LOCAL_DB_PATH=data/lite_llm_local.db
```

### Production (PostgreSQL)
```env
ENVIRONMENT=production
USE_LOCAL_DB=false
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/api_keys_db
USAGE_LOGS_DB_URL=postgresql+asyncpg://user:pass@localhost/usage_logs_db
ANALYTICS_DB_URL=postgresql+asyncpg://user:pass@localhost/analytics_db
```

## Managing Servers

### Adding a New Server

**Method 1: Edit the file directly**
```json
{
  "name": "New Custom Server",
  "endpoint": "http://localhost:8081",
  "models": ["new-model"],
  "weight": 2,
  "api_key_required": false,
  "adapter_type": "openai"
}
```

**Method 2: Use the Admin API**
```bash
curl -X POST "http://localhost:8000/admin/servers" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Custom Server",
    "endpoint": "http://localhost:8081",
    "models": ["new-model"],
    "weight": 2,
    "api_key_required": false,
    "adapter_type": "openai"
  }'
```

### Updating a Server
```bash
curl -X PUT "http://localhost:8000/admin/servers/New%20Custom%20Server" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "weight": 3,
    "models": ["new-model", "another-model"]
  }'
```

### Removing a Server
```bash
curl -X DELETE "http://localhost:8000/admin/servers/New%20Custom%20Server" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

## Configuration File Monitoring

The system automatically monitors the `servers_config.json` file for changes:
- Checks every 30 seconds for file modifications
- Automatically reloads configuration when changes are detected
- Updates the LiteLLM router with new server configurations

## Example Configurations

### Development Setup
```json
{
  "servers": [
    {
      "name": "Local Development Server",
      "endpoint": "http://localhost:8080",
      "models": ["dev-model"],
      "weight": 1,
      "api_key_required": false,
      "adapter_type": "openai",
      "description": "Local development server"
    }
  ],
  "load_balancing": {
    "strategy": "round_robin",
    "health_check_interval": 30
  },
  "api_keys": {}
}
```

### Production Setup with Load Balancing
```json
{
  "servers": [
    {
      "name": "Production Server 1",
      "endpoint": "https://api.yourserver.com",
      "models": ["production-model"],
      "weight": 3,
      "api_key_required": true,
      "adapter_type": "openai",
      "description": "Primary production server"
    },
    {
      "name": "Production Server 2",
      "endpoint": "https://api2.yourserver.com",
      "models": ["production-model"],
      "weight": 2,
      "api_key_required": true,
      "adapter_type": "openai",
      "description": "Secondary production server"
    },
    {
      "name": "Custom Embedding Service",
      "endpoint": "https://embed.yourserver.com",
      "models": ["custom-embedding"],
      "weight": 1,
      "api_key_required": true,
      "adapter_type": "custom",
      "endpoints": {
        "completion": "/generate",
        "embedding": "/embed"
      },
      "request_format": "custom",
      "response_format": "openai"
    }
  ],
  "load_balancing": {
    "strategy": "weighted",
    "health_check_interval": 30,
    "retry_attempts": 3
  },
  "api_keys": {
    "openai": "sk-your-production-key"
  }
}
```

### Mixed Environment Setup
```json
{
  "servers": [
    {
      "name": "Production OpenAI",
      "endpoint": "https://api.openai.com",
      "models": ["gpt-4", "gpt-3.5-turbo"],
      "weight": 2,
      "api_key_required": true,
      "adapter_type": "openai",
      "description": "Production OpenAI models"
    },
    {
      "name": "Local Development",
      "endpoint": "http://localhost:8080",
      "models": ["local-model"],
      "weight": 1,
      "api_key_required": false,
      "adapter_type": "openai",
      "description": "Local development server"
    }
  ],
  "load_balancing": {
    "strategy": "weighted",
    "health_check_interval": 30
  },
  "api_keys": {
    "openai": "sk-your-production-key"
  }
}
```

## API Key Management

### Storing API Keys
API keys are stored in the configuration file under the `api_keys` section. The system automatically matches servers to their appropriate API keys based on the server name or endpoint.

### API Key Matching Logic
- Servers with "openai" in name/endpoint → uses `openai` key
- Others → uses `default` key or "dummy-key"

### Security Best Practices
1. **Never commit API keys to version control**
2. **Use environment variables for production**:
   ```json
   {
     "api_keys": {
       "openai": "${OPENAI_API_KEY}"
     }
   }
   ```
3. **Use different API keys for development and production**

## Load Balancing with Multiple Servers

When multiple servers provide the same model, the system automatically load balances:

```json
{
  "servers": [
    {
      "name": "Server 1",
      "endpoint": "http://localhost:8080",
      "models": ["shared-model"],
      "weight": 3
    },
    {
      "name": "Server 2",
      "endpoint": "http://localhost:8081",
      "models": ["shared-model"],
      "weight": 1
    }
  ]
}
```

Requests for "shared-model" will be distributed:
- **75%** to Server 1 (weight 3)
- **25%** to Server 2 (weight 1)

## Troubleshooting

### Configuration File Not Found
```
FileNotFoundError: Servers config file not found: servers_config.json
```
**Solution**: Ensure the `servers_config.json` file exists in the same directory as the application.

### Invalid JSON
```
ValueError: Invalid JSON in servers config file
```
**Solution**: Validate your JSON syntax using a JSON validator or `python -m json.tool servers_config.json`.

### Server Not Responding
**Check**: 
1. Server endpoint is accessible
2. API key is correct (if required)
3. Models are available on the server
4. Server follows the expected API format for its adapter type

### Configuration Not Updating
**Check**: 
1. File permissions allow the application to read the file
2. Wait up to 30 seconds for automatic reload
3. Check application logs for configuration reload messages

### Adapter Type Mismatch
**Check**: 
1. `adapter_type` matches your server's API format
2. For custom adapters, verify `endpoints` paths are correct
3. Check `request_format` and `response_format` settings

## Advanced Configuration

### Custom Adapter Implementation
For completely custom API formats, you can extend the adapter system:

```python
# In custom_api_adapters.py
class MyCustomAdapter(BaseAPIAdapter):
    def transform_request(self, request, model):
        # Convert OpenAI format to your custom format
        return custom_request
    
    def transform_response(self, response, model):
        # Convert your format back to OpenAI format
        return openai_response

# Register the adapter
custom_api_manager.register_adapter("my_custom", MyCustomAdapter)
```

Then use it in your configuration:
```json
{
  "name": "My Custom Server",
  "endpoint": "http://localhost:9000",
  "models": ["custom-model"],
  "adapter_type": "my_custom"
}
```

## Migration from Database Configuration

If you're migrating from the previous database-based configuration:

1. **Export existing servers**:
```bash
curl -X GET "http://localhost:8000/admin/servers" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" > existing_servers.json
```
   curl -X GET "http://localhost:8000/admin/servers" \
     -H "Authorization: Bearer YOUR_ADMIN_API_KEY" > existing_servers.json
   ```

2. **Convert to file format**:
   ```bash
   # Create the new servers_config.json with your server data
   cp servers_config.json.example servers_config.json
   # Edit the file with your server configurations
   ```

3. **Update application configuration**:
   ```env
   SERVERS_CONFIG_FILE=servers_config.json
   ```

4. **Restart the application**:
   ```bash
   python app.py
   ```

The system will automatically use the file-based configuration and you can remove the old `model_servers` database table.
