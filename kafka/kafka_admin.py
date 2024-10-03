import logging
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError

# Configure logging
logging.basicConfig(
    filename='/workspaces/Real-Estate-Analyze/kafka/kafka_topic_creation.log',  # Log file path
    level=logging.INFO,  # Set log level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
    filemode="w"
)

def create_new_topic(topic_name):
    """Checks if the topic exists or not. If not, creates the topic."""
    admin_client = KafkaAdminClient(
        bootstrap_servers=['localhost:9092'],  # Kafka server
        client_id='kafka_admin_client'
    )

    try:
        # Check if the topic already exists
        existing_topics = admin_client.list_topics()
        if topic_name in existing_topics:
            logging.info(f"Topic {topic_name} already exists")
        else:
            # Create the new topic
            topic = NewTopic(name=topic_name, num_partitions=1, replication_factor=1)
            admin_client.create_topics(new_topics=[topic], validate_only=False)
            logging.info(f"Topic {topic_name} successfully created")
    except KafkaError as e:
        logging.error(f"KafkaError occurred: {e}")
    except Exception as e:
        logging.error(f"Exception occurred: {e}")
    finally:
        admin_client.close()

if __name__ == "__main__":
    create_new_topic("office_input")
    print("Successfully created!")