import os
from airflow import DAG
from datetime import datetime, timedelta

from airflow.operators.dummy import DummyOperator
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from dotenv import load_dotenv

load_dotenv()

SPARK_HOME=os.getenv("SPARK_HOME")

start_date = datetime(2024, 10, 19, 12, 20)

default_args = {
    'owner': 'train',
    'start_date': start_date,
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

with DAG('streaming_data_processing_dag', default_args=default_args, schedule_interval='@daily', catchup=False) as dag:

    # Extract
    download_data = BashOperator(task_id='download_data',
                                 bash_command='wget -O data/sensors.zip https://github.com/erkansirin78/datasets/raw/master/sensors_instrumented_in_an_office_building_dataset.zip',
                                 retries=1, retry_delay=timedelta(seconds=15))

    unzip_file = BashOperator(task_id='unzip_file',
                              bash_command='unzip ./data/sensors.zip -d ./data/',
                              retries=2, retry_delay=timedelta(seconds=15))

    remove_readme_and_zip = BashOperator(task_id='remove_readme_and_zip',
                                 bash_command='rm data/KETI/README.txt && rm data/sensors.zip')

    create_hdfs_dir = BashOperator(task_id='create_hdfs_dir',
                                    bash_command='hdfs dfs -mkdir -p /user/stream_data/',
                                    retries=2, retry_delay=timedelta(seconds=15),
                                    execution_timeout=timedelta(minutes=10))

    # 
    put_data_to_hdfs = BashOperator(task_id='put_data_to_hdfs',
                                    bash_command='hdfs dfs -copyFromLocal ./data/KETI/ /user/stream_data/',
                                    retries=2, retry_delay=timedelta(seconds=15),
                                    execution_timeout=timedelta(minutes=10))

    run_spark_transforming = BashOperator(task_id='run_spark', 
                             bash_command='python3 utils/spark_transforming.py',
                             retries=2, retry_delay=timedelta(seconds=15),
                             execution_timeout=timedelta(minutes=20))

    # copy_to_datasets = BashOperator(task_id='copy_to_datasets',
    #                                 bash_command='cp /home/train/data-generator/input/sensors.csv /home/train/datasets')
    
    
    # create_new_topic = BranchPythonOperator(task_id='create_new_topic', python_callable=create_new_topic)
    
    create_new_topic = BashOperator(task_id="create_new_topic", 
                                    bash_command = "python3 kafka/kafka_admin.py",
                                    retries=2, retry_delay=timedelta(seconds=15),
                                    execution_timeout=timedelta(minutes=20))

    topic_created = DummyOperator(task_id="topic_created",)

    topic_exists = DummyOperator(task_id="topic_already_exists")

    run_data_generator = BashOperator(task_id="run_data_generator",
                                      bash_command="~/bash/dataframe_to_kafka.sh ",
                                      execution_timeout=timedelta(minutes=15),
                                      trigger_rule='none_failed_or_skipped')

    spark_write_to_es = BashOperator(task_id="spark_write_to_es",
                                     bash_command="~/bash/spark_to_es.sh ",
                                     execution_timeout=timedelta(minutes=15),
                                     trigger_rule='none_failed_or_skipped')

    spark_write_to_minio = BashOperator(task_id="spark_write_to_minio",
                                     bash_command="~/bash/spark_to_minio.sh ",
                                     execution_timeout=timedelta(minutes=15),
                                     trigger_rule='none_failed_or_skipped')

    download_data >> unzip_file >> remove_readme_and_zip >> create_hdfs_dir >> put_data_to_hdfs >> run_spark_transforming >> create_new_topic >> [topic_created, topic_exists]
    [topic_created, topic_exists] >> run_data_generator
    [topic_created, topic_exists] >> spark_write_to_es
    [topic_created, topic_exists] >> spark_write_to_minio