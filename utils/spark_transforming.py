import findspark
findspark.init()
import findspark
from functools import reduce
from pyspark.sql import DataFrame
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DateType
from pyspark.sql.utils import AnalysisException
import logging
import os



# Set up logging
logging.basicConfig(level=logging.INFO, filename='utils/data_processing.log', filemode='w',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
INPUT_DATA_PATH = 'hdfs://127.0.0.1:9000/user/stream_data/stream_data/'
FINAL_OUTPUT_PATH = 'hdfs://127.0.0.1:9000/user/stream_data/out/'

# Initialize Spark
spark = SparkSession.builder \
    .appName("streamData") \
    .master("local[*]") \
    .config("spark.executor.memory", "8g") \
    .config("spark.executor.cores", "4") \
    .getOrCreate()

def get_hdfs_file_system():
    try:
        uri = spark.sparkContext._gateway.jvm.java.net.URI(INPUT_DATA_PATH)
        conf = spark.sparkContext._jsc.hadoopConfiguration()
        FileSystem = spark.sparkContext._gateway.jvm.org.apache.hadoop.fs.FileSystem
        return FileSystem.get(uri, conf)
    except Exception as e:
        logger.error(f"Error getting HDFS FileSystem: {e}")
        return None

def list_hdfs_directories(fs, path):
    try:
        status = fs.listStatus(spark.sparkContext._gateway.jvm.org.apache.hadoop.fs.Path(path))
        return [file.getPath().getName() for file in status if file.isDirectory()]
    except Exception as e:
        logger.error(f"Error listing HDFS directories: {e}")
        return []

def list_hdfs_files(fs, path):
    try:
        status = fs.listStatus(spark.sparkContext._gateway.jvm.org.apache.hadoop.fs.Path(path))
        return [file.getPath().getName() for file in status if file.isFile()]
    except Exception as e:
        logger.error(f"Error listing HDFS files: {e}")
        return []

def create_separate_dataframes(fs) -> dict:
    """
    Creates a dictionary that includes room numbers as keys and dataframes per room as values
    """
    dataframes = {}
    dataframes_room = {}
    columns = ['co2', 'humidity', 'light', 'pir', 'temperature']
    dirs = list_hdfs_directories(fs, INPUT_DATA_PATH)
    
    logger.info(f"Directories found: {dirs}")

    for dirname in dirs:
        data_path = f"{INPUT_DATA_PATH}/{dirname}"
        files = list_hdfs_files(fs, data_path)
        
        logger.info(f"Files found in {dirname}: {files}")
        
        count = 0
        for filename in files:
            try:
                filepath = f"{data_path}/{filename}"
                data_filename = f"{dirname}_{filename.split('.')[0]}"
                df = spark.read.csv(filepath, header=True, inferSchema=True)
                df = df.toDF('ts_min_bignt', columns[count])
                dataframes[data_filename] = df
                logger.info(f"DataFrame created for {data_filename}")
                count += 1
            except Exception as e:
                logger.error(f"Error reading file {filename} in directory {dirname}: {e}")
        
        try:
            dataframes[f'{dirname}_co2'].createOrReplaceTempView('df_co2')
            dataframes[f'{dirname}_humidity'].createOrReplaceTempView('df_humidity')
            dataframes[f'{dirname}_light'].createOrReplaceTempView('df_light')
            dataframes[f'{dirname}_pir'].createOrReplaceTempView('df_pir')
            dataframes[f'{dirname}_temperature'].createOrReplaceTempView('df_temperature')

            dataframes_room[dirname] = spark.sql('''
                SELECT
                  df_co2.*,
                  df_humidity.humidity,
                  df_light.light,
                  df_pir.pir,
                  df_temperature.temperature        
                FROM df_co2
                INNER JOIN df_humidity
                  ON df_co2.ts_min_bignt = df_humidity.ts_min_bignt
                INNER JOIN df_light
                  ON df_humidity.ts_min_bignt = df_light.ts_min_bignt
                INNER JOIN df_pir
                  ON df_light.ts_min_bignt = df_pir.ts_min_bignt
                INNER JOIN df_temperature
                  ON df_pir.ts_min_bignt = df_temperature.ts_min_bignt      
            ''')
            dataframes_room[dirname] = dataframes_room[dirname].withColumn("room", F.lit(dirname))
            logger.info(f"DataFrames for room {dirname} successfully combined")
        except KeyError as e:
            logger.error(f"KeyError: {e} - Check if all data files are present for {dirname}")
        except AnalysisException as e:
            logger.error(f"AnalysisException: {e} - Issue creating SQL view for {dirname}")
    
    return dataframes_room

def merge_dataframes(dfs):
    """
    Merges multiple dataframes vertically.
    """
    try:
        return reduce(lambda df1, df2: df1.union(df2.select(df1.columns)), dfs)
    except Exception as e:
        logger.error(f"Error in merge_dataframes: {e}")
        return None

def create_main_dataframe(separate_dataframes: dict):
    """
    Merges all per-room dataframes vertically. Creates final dataframe.
    """
    try:
        # Collect all DataFrames
        dataframes_to_concat = list(separate_dataframes.values())
        
        # Merge DataFrames
        df = merge_dataframes(dataframes_to_concat)
        df = df.sort(F.col("ts_min_bignt"))

        df = df.dropna()

        # Convert ts_min_bignt to event_ts_min correctly
        df = df.withColumn("event_ts_min", F.from_unixtime(F.col("ts_min_bignt")).cast("timestamp"))
        df = df.withColumn("event_ts_min", F.date_format(F.col("event_ts_min"), "yyyy-MM-dd HH:mm:ss"))

        logger.info("Successfully created main dataframe.")
        return df
    except Exception as e:
        logger.error(f"Error in create_main_dataframe: {e}")
        return None

def write_dataframe(df):
    """
    Writes the final dataframe to HDFS in CSV format.
    """
    try:
        df.write.parquet(FINAL_OUTPUT_PATH + "sensors.parquet", mode='overwrite')
        logger.info("Successfully written dataframe to HDFS!")
    except Exception as e:
        logger.error(f"Error in write_dataframe: {e}")

if __name__ == "__main__":
    fs = get_hdfs_file_system()
    if fs:
        room_dataframes = create_separate_dataframes(fs)
        if room_dataframes:
            main_df = create_main_dataframe(room_dataframes)
            if main_df:
                write_dataframe(main_df)
