import sys
import threading
import traceback

from reporter.HtmlReporter import HtmlReporter
from data_handler.Xlsx_File_Handler import Xlsx_File_Handler
import properties as config
from dateutil.parser import parse
from data_handler.DB_Connection_Provider import DB_Connection_Provider


class ErrorEncounterException(Exception):
    def __init__(self, message):
        super().__init__(message)


class ValidationFailedException(Exception):
    def __init__(self, message):
        super().__init__(message)


class Comparator:
    fr = None
    cursor_1 = None
    cursor_2 = None
    columns_to_exclude_in_comparison = ['year']
    out_csv = None
    xlsx_fh = None
    total_pass = 0
    total_fail = 0

    def __init__(self, report_name, table_name, number_of_records_to_match, partition_1, partition_2):
        self.report_name = report_name
        self.table_name = table_name
        self.number_of_records_to_match = number_of_records_to_match
        self.reporter = HtmlReporter(report_name=report_name)
        self.partition_1 = partition_1
        self.partition_2 = partition_2

    def validate_result(self,
                        scenario_name,
                        exp_result,
                        actual_result,
                        status=None,
                        exit_on_failure=False,
                        comment=''):

        if status is None:
            if exp_result == actual_result:
                status = 'pass'
            else:
                status = 'fail'
            if comment != '':
                status = 'error'
        self.reporter.add_scenario_result(scenario_name, str(exp_result), str(actual_result),
                                          status, comment)
        if status == 'fail' and exit_on_failure:
            self.teardown()
            raise ValidationFailedException('Validation failed! Stopped further processing!')
        elif status == 'error' and exit_on_failure:
            self.teardown()
            # raise ErrorEncounterException.ErrorEncounterException('Some error occurred! Stopped processing')

    def start_comparison(self):
        try:
            # get database connection and execute fetch query
            db_con = DB_Connection_Provider().get_db_connection()
            self.cursor_1 = db_con.cursor()
            self.cursor_2 = db_con.cursor()
            sql_query_1 = f'Select * from {self.table_name} PARTITION ({self.partition_1})'
            sql_query_2 = f'Select * from {self.table_name} PARTITION ({self.partition_2})'
            print(f'Querying DB with -- {sql_query_1}')
            rs1 = self.cursor_1.execute(sql_query_1)
            print(f'Querying DB with -- {sql_query_2}')
            rs2 = self.cursor_2.execute(sql_query_2)

            partition_1 = rs1.fetchmany(config.BUFFER_NUMBER_OF_DB_ROWS)
            partition_2 = rs2.fetchmany(config.BUFFER_NUMBER_OF_DB_ROWS)

            table_headers = [d[0].lower() for d in rs1.description]

            # adding db table columns as table headers in html report
            self.reporter.add_db_column_names_as_headers(table_headers)

            # opening an xlsx file to store the comparison result
            self.xlsx_fh = Xlsx_File_Handler(self.report_name.replace('.html', '.xlsx'),
                                             table_headers)

            number_of_row_checked = 0
            progress_update_count = int(self.number_of_records_to_match / 100)
            slider_count = 1
            print('\nComparison started ... ')
            while True and number_of_row_checked <= self.number_of_records_to_match:
                # iterate all the rows in result set and check against the file
                for index, db_row_partition_1 in enumerate(partition_1):
                    if number_of_row_checked == self.number_of_records_to_match:
                        number_of_row_checked += 1
                        break
                    if number_of_row_checked == (progress_update_count * slider_count):
                        self.update_progress(slider_count)
                        slider_count += 1

                    partition_1_row = partition_1[index]
                    partition_2_row = partition_2[index]
                    current_row_matched = True

                    unmatched_values = {}
                    unmatched_indexes = []
                    for i, header in enumerate(table_headers):
                        if header in self.columns_to_exclude_in_comparison:
                            continue
                        if str(partition_1_row[i]) == str(partition_2_row[i]):
                            continue
                        else:
                            current_row_matched = False
                            unmatched_values[header] = f'{partition_1_row[i]} <==> {partition_2_row[i]}'
                            unmatched_indexes.append(i)

                    if current_row_matched:
                        self.total_pass += 1

                        # writing comparison result in html report
                        threading.Thread(target=self.reporter.add_scenario_result_as_table_formatted_data,
                                         args=('Comparing DB row ',
                                               partition_1_row,
                                               partition_2_row,
                                               'pass')).start()

                        # writing comparison result in xlsx file
                        if self.total_pass <= config.MAX_NUMBER_OF_SUCCESS_CASES_TO_REPORT:
                            threading.Thread(target=self.xlsx_fh.write_partition1_and_partition2_row_in_xlsx_file,
                                             args=(
                                                 partition_1_row,
                                                 partition_2_row,
                                             )).start()
                    else:
                        self.total_fail += 1
                        # writing comparison result in html report
                        threading.Thread(target=self.reporter.add_scenario_result_as_table_formatted_data,
                                         args=('Comparing DB row ',
                                               partition_1_row,
                                               partition_2_row,
                                               'fail', '',
                                               unmatched_indexes
                                               )).start()

                        # writing comparison result in xlsx file
                        if self.total_fail <= config.MAX_NUMBER_OF_FAILURE_CASES_TO_REPORT:
                            threading.Thread(target=self.xlsx_fh.write_partition1_and_partition2_row_in_xlsx_file,
                                             args=(
                                                 partition_1_row,
                                                 partition_2_row,
                                                 unmatched_indexes
                                             )).start()
                    number_of_row_checked += 1

                # fetch next chuck of data from database
                partition_1 = rs1.fetchmany(config.BUFFER_NUMBER_OF_DB_ROWS)
                partition_2 = rs2.fetchmany(config.BUFFER_NUMBER_OF_DB_ROWS)

                # check if we have reached to the end of table
                if not partition_1:
                    break
            self.update_progress(100)
            print('\nprocessed data file completely.')
            self.teardown()
        except Exception as e:
            if isinstance(e, ValidationFailedException):
                return
            print('Some error occurred while processing the file.')
            print(f'full traceback --- {traceback.format_exc()}')
            self.validate_result('Checking for any error while execution',
                                 'No Error should be encountered',
                                 'Error occurred',
                                 exit_on_failure=False,
                                 comment=f'error -- {traceback.format_exc()}')
            self.teardown()

    def is_date(self, string, fuzzy=False):
        """
        Return whether the string can be interpreted as a date.

        :param string: str, string to check for date
        :param fuzzy: bool, ignore unknown tokens in string if True
        """
        try:
            parse(string, fuzzy=fuzzy)
            return True

        except ValueError:
            return False

    def teardown(self):
        self.reporter.save_report()
        if self.fr is not None:
            print('closing data file ... !')
            self.fr.close_file()
            print('data file closed successfully !!')
            del self.fr
        if self.cursor_1 is not None:
            print('closing database connection ... !')
            self.cursor_1.close()
            print('database connection closed successfully !!')
            del self.cursor_1
        if self.cursor_2 is not None:
            print('closing database connection ... !')
            self.cursor_2.close()
            print('database connection closed successfully !!')
            del self.cursor_2
        if self.out_csv is not None:
            print('Closing out_csv file ... !')
            self.out_csv.flush()
            self.out_csv.close()
            print('Closed out_csv file successfully !!')
            del self.out_csv
        if self.xlsx_fh is not None:
            self.xlsx_fh.save_xlsx_file()
            del self.xlsx_fh

    def update_progress(self, progress):
        sys.stdout.write('\r[{0}] {1}%'.format('#' * progress, progress))
        sys.stdout.flush()
