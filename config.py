import os
from dotenv import load_dotenv

load_dotenv()

# RabbitMQ Configuration
RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost:5672/')
QUEUE_NAME = 'webhook-events'

# Profile Service Configuration
PROFILE_SERVICE_URL = os.getenv('PROFILE_SERVICE_URL', 'http://localhost:8000')
PROFILE_SERVICE_API_KEY = os.getenv('PROFILE_SERVICE_API_KEY')

# API Key Configuration
API_KEY_PREFIX = 'mk_'
API_KEY_LENGTH = 64  # characters (32 bytes in hex) 