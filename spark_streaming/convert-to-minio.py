"""
This script gets the streaming data from Kafka topic, then writes it to MinIO
"""
import findspark
findspark.init()
import findspark
import sys
import warnings
import traceback
import logging
from pyspark import SparkConf, SparkContext
import os
# from dotenv import load_dotenv

# load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(funcName)s:%(levelname)s:%(message)s')

warnings.filterwarnings('ignore')
checkpointDir = "file:///tmp/streaming/minio_streaming"


def create_spark_session():
    from pyspark.sql import SparkSession
    try:
        spark = (SparkSession.builder
                 .appName("Streaming Kafka")
                 .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.3")
                 .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
                 .config("spark.jars", "/workspaces/Real-Estate-Analyze/jars/hadoop-aws-3.3.4.jar,/workspaces/Real-Estate-Analyze/jars/aws-java-sdk-bundle-1.11.1026.jar")
                 .getOrCreate())
        logging.info('Spark session successfully created')
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error(f"Couldn't create the spark session due to exception: {e}")

    return spark

def read_minio_credentials():
    import configparser

    config = configparser.RawConfigParser()
    try:
        config.read('/workspaces/Real-Estate-Analyze/aws/credentials')
        config.sections()
        accessKeyId = config.get('minio', 'aws_access_key_id')
        secretAccessKey = config.get('minio', 'aws_secret_access_key')
        logging.info('MinIO credentials obtained correctly')
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error(f"MinIO credentials couldn't be obtained due to exception: {e}")

    return accessKeyId, secretAccessKey


def load_minio_config(spark_context: SparkContext):
    accessKeyId, secretAccessKey = read_minio_credentials()
    try:
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.access.key", accessKeyId)
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.secret.key", secretAccessKey)
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.endpoint", "http://localhost:9008")
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.path.style.access", "true")
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.connection.ssl.enabled", "true")
        spark_context._jsc.hadoopConfiguration().set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        logging.info('MinIO configuration created successfully')
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        logging.error(f"MinIO config couldn't be created successfully due to exception: {e}")


def create_initial_dataframe(spark_session):
    try:
        df = (spark_session
              .readStream
              .format("kafka")
              .option("kafka.bootstrap.servers", "localhost:9092")
              .option("subscribe", "office_input")
              .option("startingOffsets", "earliest")
              .load())
        logging.info("Initial dataframe created successfully")
    except Exception as e:
        logging.warning(f"Initial dataframe couldn't be created due to exception: {e}")

    return df


def create_final_dataframe(df, spark_session):
    from pyspark.sql.types import IntegerType, FloatType, StringType
    from pyspark.sql import functions as F

    df1 = df.selectExpr("CAST(value AS STRING)")

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

    df_main = spark_session.sql("""
    select
        event_ts_min,
        co2,
        humidity,
        light,
        temperature,
        room,
        pir,
        case
        when pir > 0 then 'movement'
        else 'no_movement'
        end as if_movement
    from df2
    """)
    logging.info("Final dataframe created successfully")
    return df_main


def start_streaming(df):
    logging.info("Streaming is being started...")
    stream_query = (df.writeStream
                    .format("parquet")
                    .outputMode("append")
                    .option('header', 'true')
                    .option("checkpointLocation", checkpointDir)
                    .option("path", 's3a://datalake/office_input')
                    .start())

    return stream_query.awaitTermination()


if __name__ == '__main__':
    spark = create_spark_session()
    load_minio_config(spark.sparkContext)
    df = create_initial_dataframe(spark)
    if df.isStreaming:
        df_final = create_final_dataframe(df, spark)
        start_streaming(df_final)
    else:
        logging.info("Kafka messages is stopped.")
