import json
import sys
import time

from scripts.Comparator import Comparator


def start_execution():
    count_comparison_processed = 0
    with open('execution_info.json') as in_fh:
        execution_info = json.load(in_fh)
        for execution_info in execution_info['comparison']:
            report_name = execution_info['report_name']
            table = execution_info['table_name']
            partitions_to_compare = execution_info['partitions_to_compare']
            partition_1 = partitions_to_compare[0]
            partition_2 = partitions_to_compare[1]


            # check if number of rows to test is provided. If not provided then default will be all the rows
            number_of_records_to_match = execution_info.get('number_of_records_to_match')
            if number_of_records_to_match is not None:
                try:
                    number_of_records_to_match = int(number_of_records_to_match)
                except ValueError as error:
                    number_of_records_to_match = sys.maxsize
            else:
                number_of_records_to_match = sys.maxsize

            print(f'================ Started Comparison -- {table} {partitions_to_compare} ================')
            comp = Comparator(report_name=report_name,
                              table_name=table,
                              number_of_records_to_match=number_of_records_to_match,
                              partition_1 = partition_1,
                              partition_2 = partition_2)
            start_time = time.time()
            comp.start_comparison()
            # free up memory used by comparator object
            del comp
            end_time = time.time()
            print('=========================  Comparison Done  ========================')
            print(
                f'=======================  Comparison for this file took -- {round(end_time - start_time)} seconds !!')
            count_comparison_processed += 1
    return count_comparison_processed


if __name__ == '__main__':
    start = time.time()
    count_comparison_processed = start_execution()
    print('========================= Exiting the Comparator Program  ========================')
    end = time.time()
    print(f'program finished in --- {round(end - start, 2)} seconds')
    exit(count_comparison_processed)
