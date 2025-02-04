# Clerk Consumer Service

A service that consumes RabbitMQ messages from Clerk webhooks, generates secure API keys, and forwards user data to a profile service.

## Features

- Consumes Clerk webhook events from RabbitMQ queue
- Generates cryptographically secure API keys with `mk_` prefix
- Forwards user profile data to external profile service
- Publishes API key mappings for Redis storage
- Secure storage of API keys (hashed)
- Robust error handling and logging

## Requirements

- Python 3.8+
- RabbitMQ Server
- Access to Profile Service API

## Local Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd clerkconsumer
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the environment template and configure your variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your actual configuration values.

## Railway Deployment

1. **Prerequisites**
   - A Railway account
   - Access to a RabbitMQ instance
   - Access to Profile Service API

2. **Environment Variables**
   Set the following in Railway Dashboard:
   ```
   RABBITMQ_URL=your_rabbitmq_url
   PROFILE_SERVICE_URL=your_profile_service_url
   PROFILE_SERVICE_API_KEY=your_profile_service_api_key
   ```

3. **Deploy**
   - Connect your GitHub repository to Railway
   - Railway will automatically:
     - Detect Python
     - Install dependencies from requirements.txt
     - Start the service using the command in railway.toml

4. **Monitoring**
   - View logs in Railway Dashboard
   - Monitor service health
   - Track environment variables

## Queues

The service creates and uses two durable queues:

1. `webhook-events`: Receives Clerk webhook events
2. `api-key-mappings`: Publishes API key to user ID mappings for Redis storage

## Configuration

The following environment variables are required:

- `RABBITMQ_URL`: RabbitMQ connection URL
- `PROFILE_SERVICE_URL`: URL of the profile service API
- `PROFILE_SERVICE_API_KEY`: API key for the profile service

## Usage

Local:
```bash
python service.py
```

Railway:
The service will automatically start as a worker process.

The service will:
1. Connect to RabbitMQ
2. Listen for `user.created` events
3. Generate secure API keys
4. Forward profile data to the profile service

## API Key Format

Generated API keys follow this format:
- Prefix: `mk_`
- 64-character hex string (32 cryptographically secure random bytes)
- Example: `mk_0dbf1b1e4c8fabefa85429b5cabec282f2a1dd442dc8c0ab7a134bd77f0c6fb6`

## API Key Redis Mapping

For each generated API key, a mapping is published to RabbitMQ in the format:
```json
{
  "key": "api_key:<hashed_api_key>",
  "value": "<clerk_user_id>"
}
```

## Error Handling

The service includes comprehensive error handling:
- Failed profile service requests are logged and messages are requeued
- API key generation failures are logged
- Network connectivity issues are handled gracefully
- Failed API key mapping publications are logged and prevent profile creation

## Security

- API keys are stored only in hashed form
- Environment variables are used for sensitive configuration
- Secure random number generation for API keys
- Rate limiting and prefetch controls for RabbitMQ consumption

## Monitoring on Railway

- View logs in Railway Dashboard under the Deployments tab
- Monitor service health and uptime
- Track environment variable changes
- View deployment history