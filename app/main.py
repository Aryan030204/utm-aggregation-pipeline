import sys
import signal
import time
from kafka.admin import KafkaAdminClient, NewTopic
from kafka import errors
from app.utils.logger import get_logger
from app.utils.config import Config
from app.consumers.kafka_consumer import ConsumerService

logger = get_logger(__name__)

def ensure_kafka_topic_exists():
    topic_name = Config.KAFKA_TOPIC
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        admin_client = None
        try:
            attempts += 1
            logger.info(f"Checking Kafka topic '{topic_name}' (Attempt {attempts}/{max_attempts})...")
            admin_client = KafkaAdminClient(
                bootstrap_servers=[Config.KAFKA_BROKER],
                client_id='utm-aggregate-admin'
            )
            existing_topics = admin_client.list_topics()
            if topic_name not in existing_topics:
                logger.info(f"Kafka topic '{topic_name}' does not exist. Creating it now...")
                topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
                admin_client.create_topics(new_topics=[topic], validate_only=False)
                logger.info(f"Topic '{topic_name}' successfully created.")
            else:
                logger.info(f"Kafka topic '{topic_name}' confirmed existing.")
            
            admin_client.close()
            return # Success
            
        except errors.NoBrokersAvailable:
            if attempts == max_attempts:
                logger.error(f"Failed to connect to Kafka for topic check after {max_attempts} attempts.")
                return # We allow the service to continue to the consumer which has its own retry
            logger.warning("Kafka broker not available for topic check, retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error during Kafka topic check: {e}")
            if admin_client:
                admin_client.close()
            return

def main():
    logger.info("Initializing UTM Aggregate Pipeline Service...")
    
    if Config.FREE_RUN:
        logger.info("FREE_RUN is enabled. Bypassing Kafka and running autonomously...")
        from app.utils.dates import generate_free_run_dates
        from app.services.brand_fetcher import BrandFetcher
        from app.services.aggregate_runner import AggregateRunner
        
        target_dates = generate_free_run_dates()
        if not target_dates:
            logger.error("No valid dates generated for FREE_RUN. Exiting.")
            sys.exit(1)
            
        brands = BrandFetcher.get_all_brands()
        if not brands:
            logger.error("No valid brands fetched for FREE_RUN. Exiting.")
            sys.exit(1)
            
        for b in brands:
            brand_name = b.get("brand_name", "unknown")
            logger.info(f"FREE_RUN executing for brand: {brand_name}")
            try:
                runner = AggregateRunner(b, target_dates)
                runner.initialize()
                runner.run_aggregations()
            except Exception as run_e:
                logger.error(f"Failed processing brand {brand_name} during FREE_RUN: {run_e}")
        
        logger.info("FREE_RUN completed for all brands. Exiting autonomously.")
        sys.exit(0)
    
    # Check and create Kafka topic if missing (for normal mode)
    ensure_kafka_topic_exists()
    
    consumer_service = ConsumerService()

    def graceful_shutdown(sig, frame):
        logger.info("Graceful shutdown requested...")
        consumer_service.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        consumer_service.run()
    except Exception as e:
        logger.error(f"Fatal error in consumer service loop: {e}")
    finally:
        consumer_service.close()

if __name__ == "__main__":
    main()
