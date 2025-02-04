import json
import os
import secrets
import hashlib
import time
import structlog
import pika
import requests
from typing import Dict, Optional, Tuple
from config import (
    RABBITMQ_URL,
    QUEUE_NAME,
    API_KEY_MAPPING_QUEUE,
    PROFILE_SERVICE_URL,
    PROFILE_SERVICE_API_KEY,
    API_KEY_PREFIX,
    API_KEY_LENGTH,
)

logger = structlog.get_logger()

class ClerkConsumerService:
    def __init__(self):
        self.connection = None
        self.channel = None
        self._stored_api_keys = set()  # In-memory storage for demo; use a database in production

    def generate_api_key(self) -> Tuple[str, str]:
        """Generate a cryptographically secure API key and its hash."""
        start_time = time.time()
        
        while True:
            # Generate random bytes and convert to hex
            random_bytes = secrets.token_bytes(32)
            api_key = f"{API_KEY_PREFIX}{random_bytes.hex()}"
            
            # Generate hash
            hashed_key = self._hash_api_key(api_key)
            
            # Ensure uniqueness
            if hashed_key not in self._stored_api_keys:
                self._stored_api_keys.add(hashed_key)
                
                generation_time = (time.time() - start_time) * 1000
                logger.info("api_key_generated", generation_time_ms=generation_time)
                
                if generation_time > 100:
                    logger.warning("api_key_generation_slow", generation_time_ms=generation_time)
                
                return api_key, hashed_key

    def _hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _publish_api_key_mapping(self, hashed_key: str, user_id: str) -> bool:
        """Publish API key mapping to RabbitMQ for Redis storage."""
        try:
            # Ensure the channel is open
            if not self.channel or self.channel.is_closed:
                logger.error("channel_closed_cannot_publish_mapping")
                return False

            # Declare the queue if it doesn't exist
            self.channel.queue_declare(queue=API_KEY_MAPPING_QUEUE, durable=True)
            
            # Create the mapping message
            mapping = {
                "key": f"api_key:{hashed_key}",
                "value": user_id
            }
            
            # Publish the mapping
            self.channel.basic_publish(
                exchange='',
                routing_key=API_KEY_MAPPING_QUEUE,
                body=json.dumps(mapping),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json'
                )
            )
            
            logger.info("api_key_mapping_published", 
                       user_id=user_id,
                       queue=API_KEY_MAPPING_QUEUE)
            return True
            
        except Exception as e:
            logger.error("api_key_mapping_publish_failed", error=str(e))
            return False

    def _validate_clerk_id(self, clerk_id: str | None) -> bool:
        """Validate that the Clerk ID is present and in the correct format."""
        if not clerk_id:
            logger.error("clerk_id_missing")
            return False
        
        if not isinstance(clerk_id, str):
            logger.error("clerk_id_invalid_type", type=type(clerk_id).__name__)
            return False
            
        if not clerk_id.startswith("user_"):
            logger.error("clerk_id_invalid_format", clerk_id=clerk_id)
            return False
            
        return True

    def _extract_profile_data(self, message_data: Dict) -> Dict:
        """Extract and map profile data from the Clerk webhook message."""
        try:
            # The message has an extra 'data' wrapper
            event_data = message_data.get('data', {})
            
            # Validate message type
            event_type = event_data.get('type')  # type is in the outer data object
            if event_type != 'user.created':
                raise ValueError(f"Unexpected event type: {event_type}")

            # The actual user data is nested in data.data
            data = event_data.get('data', {})
            clerk_id = data.get('id')
            
            # Validate Clerk ID before proceeding
            if not self._validate_clerk_id(clerk_id):
                raise ValueError(f"Invalid or missing Clerk ID: {clerk_id}")
            
            # Log incoming data structure
            logger.info("extracting_profile_data", 
                       event_type=event_type,
                       user_id=clerk_id)

            # Get primary email if it exists
            email_addresses = data.get('email_addresses', [])
            primary_email_id = data.get('primary_email_address_id')
            
            email = None
            email_verified = False
            if email_addresses:
                # Try to find primary email first
                primary_email = next(
                    (email for email in email_addresses 
                     if email.get('id') == primary_email_id),
                    email_addresses[0]  # Fallback to first email if primary not found
                )
                email = primary_email.get('email_address')
                email_verified = primary_email.get('verification', {}).get('status') == 'verified'

            # Get primary phone if it exists
            phone_numbers = data.get('phone_numbers', [])
            primary_phone_id = data.get('primary_phone_number_id')
            
            phone = None
            phone_verified = False
            if phone_numbers:
                # Try to find primary phone first
                primary_phone = next(
                    (phone for phone in phone_numbers 
                     if phone.get('id') == primary_phone_id),
                    phone_numbers[0]  # Fallback to first phone if primary not found
                )
                phone = primary_phone.get('phone_number')
                phone_verified = primary_phone.get('verification', {}).get('status') == 'verified'
            
            # Generate API key and its hash
            api_key, hashed_key = self.generate_api_key()
            
            # Publish the API key mapping
            if not self._publish_api_key_mapping(hashed_key, clerk_id):
                raise ValueError("Failed to publish API key mapping")
            
            profile_data = {
                "clerkId": clerk_id,
                "email": email,
                "emailVerified": email_verified,
                "phoneNumber": phone,
                "phoneVerified": phone_verified,
                "firstName": data.get('first_name'),
                "lastName": data.get('last_name'),
                "avatarUrl": data.get('image_url') or data.get('profile_image_url'),
                "apiKey": api_key
            }

            # Log extracted data (excluding sensitive information)
            logger.info("profile_data_extracted", 
                       clerk_id=profile_data['clerkId'],
                       has_email=bool(profile_data['email']),
                       has_phone=bool(profile_data['phoneNumber']),
                       has_name=bool(profile_data['firstName'] or profile_data['lastName']),
                       email_verified=profile_data['emailVerified'],
                       phone_verified=profile_data['phoneVerified'])

            return profile_data
        except Exception as e:
            logger.error("profile_data_extraction_failed", 
                        error=str(e),
                        data_keys=list(message_data.keys()) if isinstance(message_data, dict) else None)
            raise

    def _forward_to_profile_service(self, profile_data: Dict) -> bool:
        """Forward the profile data to the external profile service."""
        try:
            if not PROFILE_SERVICE_URL:
                logger.error("profile_service_url_missing")
                return False

            endpoint = f"{PROFILE_SERVICE_URL.rstrip('/')}/api/profiles/me"
            logger.info("sending_profile_data", endpoint=endpoint)

            response = requests.post(
                endpoint,
                json=profile_data,
                headers={
                    "x-api-key": PROFILE_SERVICE_API_KEY,
                    "Content-Type": "application/json"
                },
                timeout=10
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error("profile_service_request_failed", 
                        error=str(e),
                        endpoint=endpoint if 'endpoint' in locals() else None,
                        status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None)
            return False
        except Exception as e:
            logger.error("unexpected_error", error=str(e))
            return False

    def _process_message(self, ch, method, properties, body):
        """Process incoming RabbitMQ messages."""
        try:
            message = json.loads(body)
            
            # Only process user.created events
            # Note: eventType is in the outer object now
            if message.get('eventType') != 'user.created':
                logger.info("skipping_non_user_created_event", 
                          event_type=message.get('eventType'))
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # Extract and process profile data
            profile_data = self._extract_profile_data(message)
            
            # Forward to profile service
            if self._forward_to_profile_service(profile_data):
                logger.info("profile_created_successfully", 
                          clerk_id=profile_data['clerkId'],
                          email=bool(profile_data['email']),
                          phone=bool(profile_data['phoneNumber']))
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                # Negative acknowledgment to retry later
                logger.warning("profile_creation_failed", clerk_id=profile_data['clerkId'])
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
        except Exception as e:
            logger.error("message_processing_failed", error=str(e))
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start(self):
        """Start consuming messages from RabbitMQ."""
        try:
            # Connect to RabbitMQ
            self.connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            self.channel = self.connection.channel()
            
            # Declare both queues
            # Main webhook events queue
            self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
            
            # API key mapping queue
            self.channel.queue_declare(queue=API_KEY_MAPPING_QUEUE, durable=True)
            logger.info("queues_declared", 
                       webhook_queue=QUEUE_NAME, 
                       mapping_queue=API_KEY_MAPPING_QUEUE)
            
            # Set up consumer
            self.channel.basic_qos(prefetch_count=1)
            self.channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=self._process_message
            )
            
            logger.info("service_started", queue=QUEUE_NAME)
            self.channel.start_consuming()
            
        except Exception as e:
            logger.error("service_error", error=str(e))
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            raise

    def stop(self):
        """Stop the service gracefully."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("service_stopped")

if __name__ == "__main__":
    service = ClerkConsumerService()
    try:
        service.start()
    except KeyboardInterrupt:
        service.stop() 