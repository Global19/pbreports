import os
import logging
import tempfile
import unittest
import json
from pprint import pformat

from pbcommand.models.report import Report
import pbcommand.testkit

from pbreports.report.amplicon_analysis_timing import run_to_report
from base_test_case import LOCAL_DATA, run_backticks, validate_report_complete

log = logging.getLogger(__name__)

_NAME = 'amplicon_analysis_timing'
DATA_DIR = os.path.join(LOCAL_DATA, _NAME)


class TestAmpliconAnalysisTimingReport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        log_file_name = 'amplicon_analysis.log'
        cls.log_file = tempfile.NamedTemporaryFile(suffix=".log")
        cls.input_log_file = os.path.join(DATA_DIR, log_file_name)
        log.info("Using {l}".format(l=cls.input_log_file))

    def test_basic(self):
        report = run_to_report(self.input_log_file)
        validate_report_complete(self, report)
        self.assertTrue(isinstance(report, Report))
        log.info(pformat(report.to_dict()))
        self.assertIsNotNone(report)


class TestIntegrationAmpliconAnalysisTimingReport(TestAmpliconAnalysisTimingReport):

    def test_basic(self):
        report_json = tempfile.NamedTemporaryFile(suffix=".json").name
        exe = "amplicon_analysis_timing_report"
        cmd = "{e} --debug {l} {r}".format(e=exe,
                                           l=self.input_log_file,
                                           r=report_json)
        exit_code = run_backticks(cmd)
        self.assertEqual(exit_code, 0)

        with open(report_json, 'r') as f:
            d = json.loads(f.read())

        self.assertIsNotNone(d)

        # cleanup
        if os.path.exists(report_json):
            os.remove(report_json)


class TestAmpliconAnalysisTiming(pbcommand.testkit.PbTestApp):
    DATA_DIR = os.path.join(LOCAL_DATA, "amplicon_analysis_timing")
    log_file = os.path.join(DATA_DIR, "amplicon_analysis.log")
    t = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    t.close()
    report_json = t.name
    DRIVER_BASE = "python -m pbreports.report.amplicon_analysis_timing "
    DRIVER_EMIT = DRIVER_BASE + " --emit-tool-contract "
    DRIVER_RESOLVE = DRIVER_BASE + " --resolved-tool-contract "
    REQUIRES_PBCORE = False
    INPUT_FILES = [
        log_file,
    ]
    OUTPUT_FILES = [report_json]
    TASK_OPTIONS = {}
