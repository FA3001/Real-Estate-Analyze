/workspaces/Real-Estate-Analyze/kafka_2.12-3.8.0/bin/zookeeper-server-start.sh /workspaces/Real-Estate-Analyze/kafka_2.12-3.8.0/config/zookeeper.properties
/workspaces/Real-Estate-Analyze/kafka_2.12-3.8.0/bin/zookeeper-server-stop.sh
kafka_2.12-3.8.0/bin/kafka-server-start.sh /workspaces/Real-Estate-Analyze/kafka_2.12-3.8.0/config/server.properties
kafka_2.12-3.8.0/bin/kafka-server-stop.sh



#---------------------------------------------------------------------------
# installing java11 & pyspark
wget https://download.java.net/java/GA/jdk11/9/GPL/openjdk-11.0.2_linux-x64_bin.tar.gz
tar zxfv /workspaces/streaming_data/openjdk-11.0.2_linux-x64_bin.tar.gz

export JAVA_HOME="/path/to/jdk-11.0.2"
export PATH="${JAVA_HOME}/bin:${PATH}"


wget https://dlcdn.apache.org/spark/spark-3.4.3/spark-3.4.3-bin-hadoop3.tgz
tar zxfv spark-3.4.3-bin-hadoop3.tgz
rm spark-3.4.3-bin-hadoop3.tgz

export SPARK_HOME="/path/to/spark-3.4.3-bin-hadoop3"
export PATH="${SPARK_HOME}/bin:${PATH}"

# installing jupyter
mkdir notebook
cd notebook
virtualenv jupyterenv
source jupyterenv/bin/activate
pip install jupyter
jupyter notebook


python3 /path/to/kafka_producer.py -i hdfs://localhost:9000/user/stream_data/out/sensors.parquet -e parquet -t office_input -rst 2
wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar
wget https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.1026/aws-java-sdk-bundle-1.11.1026.jar