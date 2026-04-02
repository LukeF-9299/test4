# Quick Start Guide

## 1. Setup Environment

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

Required environment variables:
```env
ENVIRONMENT=development
USE_LOCAL_DB=true
API_SECRET_KEY=your-secret-key-here
```

For production:
```env
ENVIRONMENT=production
USE_LOCAL_DB=false
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/api_keys_db
USAGE_LOGS_DB_URL=postgresql+asyncpg://user:password@localhost:5432/usage_logs_db
ANALYTICS_DB_URL=postgresql+asyncpg://user:password@localhost:5432/analytics_db
```

## 2. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Dashboard dependencies (optional)
cd dashboard
npm install
cd ..
```

## 3. Configure Your Servers

Edit `servers_config.json` to add your model servers:

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

### Server Configuration Options

- **adapter_type**: `"openai"` (OpenAI-compatible), `"custom"` (custom API), `"huggingface"` (HF format)
- **weight**: Load balancing weight (higher = more traffic)
- **api_key_required**: Set to `true` if your server needs authentication

## 4. Start the Service

```bash
# Start the API service
python app.py
```

The API will be available at `http://localhost:8000`

## 5. Test the API

### Health Check
```bash
curl http://localhost:8000/health
```

### Create Admin API Key
```bash
curl -X POST "http://localhost:8000/admin/api-keys" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Admin Key",
    "expires_in_days": 365
  }'
```

Save the returned API key for authentication.

### Test Chat Completion
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-name",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Test Embeddings
```bash
curl -X POST "http://localhost:8000/v1/embeddings" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-embedding-model",
    "input": "Your text to embed"
  }'
```

### List Available Models
```bash
curl -X GET "http://localhost:8000/v1/models" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

## 6. Manage Servers via API

### Add Server via API
```bash
curl -X POST "http://localhost:8000/admin/servers" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Custom Server",
    "endpoint": "http://localhost:8081",
    "models": ["custom-model"],
    "weight": 2,
    "api_key_required": false,
    "adapter_type": "openai"
  }'
```

### List Servers
```bash
curl -X GET "http://localhost:8000/admin/servers" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

### Update Server
```bash
curl -X PUT "http://localhost:8000/admin/servers/New%20Custom%20Server" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "weight": 3,
    "models": ["custom-model", "another-model"]
  }'
```

### Remove Server
```bash
curl -X DELETE "http://localhost:8000/admin/servers/New%20Custom%20Server" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

## 7. Start Admin Dashboard (Optional)

```bash
cd dashboard
npm run dev
```

Dashboard will be available at `http://localhost:3000`

## 8. Production Deployment

### Using Docker
```bash
# Build image
docker build -t lite-llm-api .

# Run container
docker run -p 8000:8000 --env-file .env lite-llm-api
```

### Using Systemd
```bash
# Create service file
sudo nano /etc/systemd/system/lite-llm-api.service
```

Service file content:
```ini
[Unit]
Description=Lite LLM API Service
After=network.target

[Service]
Type=simple
User=api-user
WorkingDirectory=/path/to/lite-llm-api
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable lite-llm-api
sudo systemctl start lite-llm-api
```

## Troubleshooting

### Database Connection Issues
1. Verify PostgreSQL is running: `sudo systemctl status postgresql`
2. Check environment variables in `.env`
3. For local development, ensure `USE_LOCAL_DB=true`

### Server Configuration Issues
1. Check `servers_config.json` syntax
2. Verify server endpoints are accessible
3. Check adapter type matches your server format

### Performance Issues
1. Monitor server health: `curl -X GET "http://localhost:8000/admin/health"`
2. Check load balancing weights
3. Review analytics for bottlenecks

## Monitoring

### Check Logs
```bash
# API logs
tail -f /var/log/lite-llm-api.log

# System logs
journalctl -u lite-llm-api -f
```

### Health Monitoring
```bash
# Service health
curl http://localhost:8000/health

# Admin health status
curl -X GET "http://localhost:8000/admin/health" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

### Database Monitoring
```bash
# Check database sizes (PostgreSQL)
psql -c "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) FROM pg_database;"

# Check active connections
psql -c "SELECT state, count(*) FROM pg_stat_grouping GROUP BY state;"
```

## File Configuration Management

### Edit Servers Directly
```bash
# Edit the configuration file
nano servers_config.json

# Changes auto-reload within 30 seconds
```

### Backup Configuration
```bash
cp servers_config.json servers_config.json.backup
```

### Validate Configuration
```bash
# Check JSON syntax
python -m json.tool servers_config.json
```
