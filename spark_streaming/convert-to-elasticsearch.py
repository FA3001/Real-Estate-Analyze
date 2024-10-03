"""
This script gets the streaming data from Kafka topic, then writes it to Elasticsearch
"""

import findspark
findspark.init()
import findspark
import sys
import warnings
import traceback
import logging
from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(funcName)s:%(levelname)s:%(message)s')

warnings.filterwarnings('ignore')
checkpointDir = "file:///tmp/streaming/kafka_office_input" 

# Below creates the format for office_input index.
office_input_index = {
    "settings": {
        "index": {
            "analysis": {
                "analyzer": {
                    "custom_analyzer":
                        {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase", "custom_edge_ngram", "asciifolding"
                            ]
                        }
                },
                "filter": {
                    "custom_edge_ngram": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 10
                    }
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "if_movement": {"type": "keyword"},
            "co2": {"type": "float"},
            "humidity": {"type": "float"},
            "light": {"type": "float"},
            "pir": {"type": "float"},
            "temperature": {"type": "float"},
            "room": {"type": "keyword"},
            "event_ts_min": {"type": "date",
            "format": "yyyy-MM-d hh:mm:ss||yyyy-MM-dd hh:mm:ss||yyyy-MM-dd HH:mm:ss||yyyy-MM-d HH:mm:ss",
            "ignore_malformed": "true"
            }
        }
    }
}

def create_spark_session():
    """
    Creates the Spark Session with suitable configs.
    """
    try:
        # Spark session is established with elasticsearch and kafka jars. Suitable versions can be found in Maven repository.
        spark = (SparkSession.builder
                 .appName("Streaming Kafka-Spark")
                 .config("spark.jars.packages", "org.elasticsearch:elasticsearch-spark-30_2.12:8.14.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3")
                 .config("spark.driver.memory", "4096m")
                 .config("spark.sql.shuffle.partitions", 4)
                 .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
                 .config("spark.sql.streaming.schemaInference", "true")
                 .getOrCreate())
        logging.info('Spark session created successfully')
    except Exception:
        traceback.print_exc(file=sys.stderr)  # To see traceback of the error.
        logging.error("Couldn't create the spark session")

    return spark

def create_initial_dataframe(spark_session):
    """
    Reads the streaming data and creates the initial dataframe accordingly.
    """
    try:
        # Gets the streaming data from topic office_input.
        df = spark_session \
          .readStream \
          .format("kafka") \
          .option("kafka.bootstrap.servers", "localhost:9092") \
          .option("subscribe", "office_input") \
          .load()
        logging.info("Initial dataframe created successfully")
    except Exception as e:
        logging.warning(f"Initial dataframe couldn't be created due to exception: {e}")

    return df

def create_final_dataframe(df, spark_session):
    """
    Modifies the initial dataframe, and creates the final dataframe.
    """
    from pyspark.sql.types import IntegerType, FloatType, StringType
    from pyspark.sql import functions as F

    df1 = df.selectExpr("CAST(value AS STRING)")  # Get only the value part of the topic message.

    df2 = df1.withColumn("ts_min_bignt", F.split(F.col("value"), ",")[0].cast(IntegerType())) \
        .withColumn("co2", F.split(F.col("value"), ",")[1].cast(FloatType())) \
        .withColumn("humidity", F.split(F.col("value"), ",")[2].cast(FloatType())) \
        .withColumn("light", F.split(F.col("value"), ",")[3].cast(FloatType())) \
        .withColumn("pir", F.split(F.col("value"), ",")[4].cast(FloatType())) \
        .withColumn("temperature", F.split(F.col("value"), ",")[5].cast(FloatType())) \
        .withColumn("room", F.split(F.col("value"), ",")[6].cast(StringType())) \
        .withColumn("event_ts_min", F.split(F.col("value"), ",")[7].cast(StringType())) \
        .drop(F.col("value")) 

    df2.createOrReplaceTempView("df2")

    # Below adds the if_movement column. This column shows the situation of the movement depending on the pir column.
    df_main = spark_session.sql("""
    select
    case
        when pir > 0 then 'movement'
        else 'no_movement'
      end as if_movement,
      co2,
      humidity,
      light,
      pir,
      temperature,
      room,
      event_ts_min
    from df2
    """)
    logging.info("Final dataframe created successfully")
    return df_main

def create_elasticsearch_connection():
    """
    Creates the ES connection.
    """
    from elasticsearch import Elasticsearch
    try:
        es = Elasticsearch("http://localhost:9200")
        logging.info(f"Connection {es} created successfully")  # Prints the connection details.
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error("Couldn't create the Elasticsearch connection")

    return es

def check_if_index_exists(es):
    """
    Checks if index office_input exists. If not, creates it and prints message accordingly.
    """
    if es.indices.exists(index="office_input"):
        print("Index office_input already exists")
        logging.info("Index office_input already exists")
    else:
        es.indices.create(index="office_input", body=office_input_index)
        print("Index office_input created")
        logging.info("Index office_input created")

def start_streaming(df):
    """
    Starts the streaming to index office_input in Elasticsearch.
    """
    logging.info("Streaming is being started...")
    my_query = (df.writeStream
                   .format("org.elasticsearch.spark.sql")
                   .outputMode("append")
                   .option("es.nodes.wan.only", "true")
                   .option("es.nodes", "localhost")
                   .option("es.port", "9200")
                   .option("es.resource", "office_input")
                   .option("checkpointLocation", checkpointDir)
                   .start())

    return my_query.awaitTermination()

if __name__ == '__main__':
    spark = create_spark_session()
    df = create_initial_dataframe(spark)
    df_final = create_final_dataframe(df, spark)
    es = create_elasticsearch_connection()
    check_if_index_exists(es)
    start_streaming(df_final)
