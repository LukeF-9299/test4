# Lite LLM API Service

A scalable API gateway for OpenAI-compatible model servers with built-in load balancing, usage analytics, and admin management.

## Features

- **Load Balancing**: Health-based weighted round-robin distribution across multiple model servers
- **OpenAI Compatible**: Drop-in replacement for OpenAI API endpoints
- **Streaming Support**: Full support for streaming responses
- **Usage Analytics**: Comprehensive logging and reporting with configurable retention
- **API Key Management**: Secure API key generation, rotation, and revocation
- **Admin Dashboard**: Web interface for monitoring and management
- **Multi-Database**: Separate PostgreSQL databases for different data needs
- **High Performance**: Built with FastAPI and async operations for 1M+ calls/week

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│  Lite LLM API   │───▶│ Model Servers   │
│                 │    │     Service     │    │ (OpenAI API)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  PostgreSQL     │
                       │  Databases      │
                       │ ┌─────────────┐ │
                       │ │ API Keys    │ │
                       │ │ Usage Logs  │ │
                       │ │ Analytics   │ │
                       │ └─────────────┘ │
                       └─────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Node.js 16+ (for admin dashboard)

### Installation

1. **Clone and setup**:
```bash
git clone <repository>
cd lite-llm-api-service
pip install -r requirements.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your database URLs and settings
```

3. **Setup databases**:
```bash
python setup_database.py
```

4. **Start the service**:
```bash
python app.py
```

The API will be available at `http://localhost:8000`

### Configuration

Edit `.env` file:

```env
# Database URLs
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/api_keys_db
USAGE_LOGS_DB_URL=postgresql+asyncpg://user:pass@localhost/usage_logs_db
ANALYTICS_DB_URL=postgresql+asyncpg://user:pass@localhost/analytics_db

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=your-secret-key

# LiteLLM
LITELLM_LOAD_BALANCING_STRATEGY=weighted
LITELLM_HEALTH_CHECK_INTERVAL=30

# Data Retention (days)
DATA_RETENTION_DAYS=180
```

## API Usage

### OpenAI Compatible Endpoints

#### Chat Completions
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

#### Streaming Chat Completions
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

#### List Models
```bash
curl -X GET "http://localhost:8000/v1/models" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Admin Endpoints

#### Create API Key
```bash
curl -X POST "http://localhost:8000/admin/api-keys" \
  -H "Authorization: Bearer ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Application",
    "expires_in_days": 365
  }'
```

#### Register Model Server
```bash
curl -X POST "http://localhost:8000/admin/servers" \
  -H "Authorization: Bearer ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-4 Server",
    "endpoint": "https://api.openai.com",
    "models": ["gpt-4", "gpt-4-turbo"],
    "weight": 2
  }'
```

#### Get Usage Statistics
```bash
curl -X GET "http://localhost:8000/admin/usage-stats?start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer ADMIN_API_KEY"
```

## Load Balancing Strategies

The service supports multiple load balancing strategies via LiteLLM:

- **weighted**: Distribute requests based on server weights
- **round_robin**: Equal distribution across servers
- **least_busy**: Route to server with fewest active requests
- **health_check_based**: Prioritize healthy servers

Configure in `.env`:
```env
LITELLM_LOAD_BALANCING_STRATEGY=weighted
```

## Database Schema

### API Keys Database
- `api_keys`: Store API keys with metadata
- `api_key_rotations`: Track key rotation history

### Usage Logs Database
- `api_calls`: Log every API request with timing and token usage

### Analytics Database
- `daily_usage`: Aggregated daily statistics
- `model_servers`: Registered model servers
- `hourly_metrics`: Detailed hourly performance metrics

## Analytics & Reporting

### Automated Aggregations
- **Hourly**: Request counts, token usage, response times
- **Daily**: Summarized usage statistics
- **Retention**: Configurable data cleanup (default 180 days)

### Available Reports
- Usage reports by date range
- Model performance comparison
- Hourly metrics analysis
- API key usage statistics

## Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Admin Health Status
```bash
curl -X GET "http://localhost:8000/admin/health" \
  -H "Authorization: Bearer ADMIN_API_KEY"
```

### Dashboard Data
```bash
curl -X GET "http://localhost:8000/admin/dashboard" \
  -H "Authorization: Bearer ADMIN_API_KEY"
```

## Performance

The service is designed to handle:
- **1M+ API calls per week** (~150 calls/minute)
- **Sub-50ms gateway overhead**
- **99.9% uptime** with automatic failover
- **Concurrent streaming** for multiple clients

## Security

- **API Key Authentication**: Bearer token authentication
- **Key Hashing**: bcrypt hashing for stored keys
- **Configurable CORS**: Secure cross-origin requests
- **Request Logging**: Security audit trail

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
isort .
```

### Database Migrations
```bash
alembic upgrade head
```

## Production Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "app.py"]
```

### Environment Variables for Production
- Use strong `API_SECRET_KEY`
- Configure proper database connections
- Set appropriate `DATA_RETENTION_DAYS`
- Enable HTTPS with reverse proxy
- Configure monitoring and alerting

## Admin Dashboard

A React-based admin dashboard provides:
- API key management
- Server health monitoring
- Usage analytics charts
- Real-time metrics

To build and run:
```bash
cd dashboard
npm install
npm run build
npm start
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check PostgreSQL is running
   - Verify connection strings in `.env`
   - Ensure database user has proper permissions

2. **LiteLLM Configuration Errors**
   - Verify model server endpoints are accessible
   - Check API keys for model servers
   - Review load balancing strategy

3. **High Memory Usage**
   - Adjust database connection pool sizes
   - Reduce data retention period
   - Monitor for memory leaks

### Logs

Structured JSON logs are output for:
- API requests and responses
- Database operations
- Load balancing decisions
- Error conditions

Enable debug logging:
```env
LOG_LEVEL=DEBUG
LITELLM_DEBUG=true
```

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review application logs
3. Create an issue with detailed information

---

**Built with FastAPI, LiteLLM, and PostgreSQL**
