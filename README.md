# Clerk Consumer Service

A service that consumes RabbitMQ messages from Clerk webhooks, generates secure API keys, and forwards user data to a profile service.

## Features

- Consumes Clerk webhook events from RabbitMQ queue
- Generates cryptographically secure API keys with `mk_` prefix
- Forwards user profile data to external profile service
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

1. Install Railway CLI (optional):
   ```bash
   npm i -g @railway/cli
   ```

2. Initialize Railway project:
   ```bash
   railway login
   railway init
   ```

3. Set up environment variables in Railway Dashboard:
   - Go to your project in Railway Dashboard
   - Navigate to Variables tab
   - Add the following variables:
     - `RABBITMQ_URL`: Your RabbitMQ connection URL
     - `PROFILE_SERVICE_URL`: Your profile service URL
     - `PROFILE_SERVICE_API_KEY`: Your profile service API key

4. Deploy to Railway:
   ```bash
   railway up
   ```
   
   Or connect your GitHub repository to Railway for automatic deployments.

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

## Error Handling

The service includes comprehensive error handling:
- Failed profile service requests are logged and messages are requeued
- API key generation failures are logged
- Network connectivity issues are handled gracefully

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