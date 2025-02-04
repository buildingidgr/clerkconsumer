import os
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

load_dotenv()

# RabbitMQ Configuration
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
QUEUE_NAME = 'webhook-events'
API_KEY_MAPPING_QUEUE = 'api-key-mappings'  # Queue for API key to user ID mappings

# Profile Service Configuration
def ensure_https_scheme(url: str) -> str:
    """Ensure the URL has https:// scheme."""
    if not url:
        return url
    if not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url

PROFILE_SERVICE_URL = ensure_https_scheme(os.getenv('PROFILE_SERVICE_URL', 'http://localhost:8000'))
PROFILE_SERVICE_API_KEY = os.getenv('PROFILE_SERVICE_API_KEY')

# API Key Configuration
API_KEY_PREFIX = 'mk_'
API_KEY_LENGTH = 64  # characters (32 bytes in hex) 