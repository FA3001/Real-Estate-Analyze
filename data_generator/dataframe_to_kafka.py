import findspark
from kafka import KafkaProducer
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import concat_ws
import logging
import os
# from dotenv import load_dotenv

# load_dotenv()

SPARK_HOME = os.getenv("SPARK_HOME")

# Set up logging
logging.basicConfig(level=logging.INFO, filemode="w")
logger = logging.getLogger(__name__)

# Create a file handler
file_handler = logging.FileHandler('kafka/data_to_kafka.log')
file_handler.setLevel(logging.INFO)

# Create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

# Initialize Spark
findspark.init(SPARK_HOME)
spark = SparkSession.builder \
    .appName("Dataframe to Kafka") \
    .master("local[8]") \
    .config("spark.executor.memory", "4g") \
    .config("spark.executor.cores", "2") \
    .getOrCreate()

class DataFrameToKafka:
    def __init__(self, input, sep, kafka_sep, row_sleep_time, source_file_extension, bootstrap_servers,
                 topic, repeat, shuffle, key_index, excluded_cols, limit_rows):
        self.input = input
        logger.info(f"Input file: {self.input}")
        self.sep = sep
        logger.info(f"CSV separator: {self.sep}")
        self.kafka_sep = kafka_sep
        logger.info(f"Kafka separator: {self.kafka_sep}")
        self.row_sleep_time = row_sleep_time
        logger.info(f"Row sleep time: {self.row_sleep_time}")
        self.repeat = repeat
        logger.info(f"Repeat: {self.repeat}")
        self.shuffle = shuffle
        logger.info(f"Shuffle: {self.shuffle}")
        self.excluded_cols = excluded_cols
        logger.info(f"Excluded columns: {self.excluded_cols}")
        self.limit_rows = limit_rows
        logger.info(f"Limit rows: {self.limit_rows}")
        self.df = self.read_source_file(source_file_extension)
        self.topic = topic
        logger.info(f"Kafka topic: {self.topic}")
        self.key_index = key_index
        logger.info(f"Key index: {self.key_index}")
        logger.info(f"Bootstrap servers: {bootstrap_servers}")
        try:
            self.producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
        except:
            logger.info("No Broker available")

    def turn_df_to_str(self, df):
        """
        Converts all columns into a single column of strings with a specified separator.
        :param df: Spark DataFrame
        :return: Column expression of concatenated values
        """
        return concat_ws(self.kafka_sep, *df.columns)

    def read_source_file(self, extension='csv'):
        if extension == 'csv':
            df = spark.read.csv(self.input, header=True, sep=self.sep, inferSchema=True)
        elif extension == 'parquet':
            df = spark.read.parquet(self.input)
        else:
            raise ValueError("Unsupported file extension")

        # Drop rows with any null values
        df = df.dropna()

        # Exclude columns and create the value column
        columns_to_write = [col for col in df.columns if col not in self.excluded_cols]
        logger.info(f"Columns to write: {columns_to_write}")
        df = df.select(columns_to_write)
        df = df.withColumn('value', self.turn_df_to_str(df))

        # Limit the number of rows to the specified limit
        if self.limit_rows > 0:
            df = df.limit(self.limit_rows)

        return df

    def df_to_kafka(self):
        sayac = 0
        df_size = self.df.count() * self.repeat
        total_time = self.row_sleep_time * df_size

        for i in range(0, self.repeat):
            for row in self.df.collect():
                key = str(row[self.key_index]).encode() if self.key_index != 1000 else str(row[0]).encode()
                value = row['value'].encode()
                self.producer.send(self.topic, key=key, value=value)
                self.producer.flush()
                time.sleep(self.row_sleep_time)
                sayac += 1
                remaining_per = 100 - (100 * (sayac / df_size))
                remaining_time_secs = (total_time - (self.row_sleep_time * sayac))
                remaining_time_mins = remaining_time_secs / 60
                logger.info(f"{key.decode()} - {value.decode()}")
                logger.info(f"{sayac}/{df_size} processed, {remaining_per:.2f}% remaining, "
                            f"{remaining_time_mins:.2f} minutes estimated time left.")

            if sayac >= df_size:
                break
        self.producer.close()