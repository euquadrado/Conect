import os
import sys
import traceback
from pathlib import Path

report = os.environ.get('CONECT_SELF_TEST_REPORT')
if report:
    def report_failure(kind, value, tb):
        Path(report).write_text(''.join(traceback.format_exception(kind, value, tb)), encoding='utf-8')
        os._exit(1)
    sys.excepthook = report_failure
