import argparse
import sys
import os
import findspark
findspark.init()
import findspark
# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_generator.dataframe_to_kafka import DataFrameToKafka

if __name__ == "__main__":
    # Boolean options parser
    def str2bool(v):
        if isinstance(v, bool):
            return v
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    parse = argparse.ArgumentParser()
    parse.add_argument("-i", "--input", required=False, type=str, default="input/iris.csv",
                    help="Source data path. Default: ./input/iris.csv")
    parse.add_argument("-s", "--sep", required=False, type=str, default=",",
                    help="Source data file delimiter. Default: ,")
    parse.add_argument("-e", "--source_file_extension", required=False, type=str, default="csv",
                    help="Extension of data file (csv or parquet). Default: csv")
    parse.add_argument("-ks", "--kafka_sep", required=False, type=str, default=",",
                    help="Kafka value separator. What should be the sep in Kafka. Default: ,")
    parse.add_argument("-rst", "--row_sleep_time", required=False, type=float, default=0.5,
                    help="Sleep time in seconds per row. Default: 0.5")
    parse.add_argument("-t", "--topic", required=False, type=str, default="test1",
                    help="Kafka topic. Which topic to produce. Default: test1")
    parse.add_argument("-b", "--bootstrap_servers", required=False, nargs='+', default=["localhost:9092"],
                    help="Kafka bootstrap servers and port in a python list. Default: [localhost:9092]")
    parse.add_argument("-r", "--repeat", required=False, type=int, default=1,
                    help="How many times to repeat dataset. Default: 1")
    parse.add_argument("-shf", "--shuffle", required=False, type=str2bool, default=False,
                    help="Shuffle the rows?. Default: False")
    parse.add_argument("-k", "--key_index", required=False, type=int, default=1000,
                    help="Which column will be sent as key to Kafka? If not used this option, pandas dataframe index will be sent. Default: 1000 indicates pandas index will be used.")
    parse.add_argument("-exc", "--excluded_cols", required=False, nargs='+', default=['it_is_impossible_column'],
                    help="The columns not to write log file?. Default ['it_is_impossible_column']. Ex: -exc 'Species' 'PetalWidthCm'")
    parse.add_argument("-l", "--limit_rows", required=False, type=int, default=0,
                    help="Limit the number of rows to process. Default: 0")

    args = vars(parse.parse_args())

    df_to_kafka = DataFrameToKafka(
        input=args['input'],
        sep=args['sep'],
        kafka_sep=args['kafka_sep'],
        row_sleep_time=args['row_sleep_time'],
        source_file_extension=args['source_file_extension'],
        bootstrap_servers=args['bootstrap_servers'],
        topic=args['topic'],
        repeat=args['repeat'],
        shuffle=args['shuffle'],
        key_index=args['key_index'],
        excluded_cols=args['excluded_cols'],
        limit_rows=args['limit_rows']
    )
    df_to_kafka.df_to_kafka()