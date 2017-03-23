#!/usr/bin/env python

"""
Generates the SAT metric performance attributes
"""

from collections import defaultdict
import logging
import os
import sys

from pbcommand.models.report import Attribute, Report, PbReportError
from pbcommand.models import FileTypes, get_pbparser
from pbcommand.pb_io.report import load_report_from_json
from pbcommand.common_options import add_debug_option
from pbcommand.cli import pbparser_runner
from pbcommand.utils import setup_log
from pbcore.io import AlignmentSet

from pbreports.util import movie_to_cell, add_base_options_pbcommand
from pbreports.io.specs import *

log = logging.getLogger(__name__)

__version__ = '0.1'


class Constants(object):
    TOOL_ID = "pbreports.tasks.sat_report"
    DRIVER_EXE = "python -m pbreports.report.sat --resolved-tool-contract "
    R_ID = "sat"
    A_INSTRUMENT = "instrument"
    A_COVERAGE = "coverage"
    A_CONCORDANCE = "concordance"
    A_READLENGTH = "mapped_readlength_mean"
    A_READS = "reads_in_cell"

    V_COVERAGE = "weighted_mean_bases_called"
    V_CONCORDANCE = "weighted_mean_concordance"
    M_READLENGTH = "mapped_readlength_mean"

spec = load_spec(Constants.R_ID)


def make_sat_report(aligned_reads_file, mapping_stats_report, variants_report, report, output_dir):
    """
    Entry to report.
    :param aligned_reads_file: (str) path to aligned_reads.xml
    :param mapping_stats_report: (str) path to mapping stats json report
    :param variants_report: (str) path to variants report
    """
    _validate_inputs([('aligned_reads_file', aligned_reads_file),
                      ('mapping_stats_report', mapping_stats_report),
                      ('variants_report', variants_report)])

    d_map = _get_mapping_stats_data(mapping_stats_report)
    reads, inst = _get_reads_info(aligned_reads_file)
    d_bam = _get_read_hole_data(reads, inst)
    d_var = _get_variants_data(variants_report)
    ds = AlignmentSet(aligned_reads_file)

    rpt = Report(Constants.R_ID, dataset_uuids=(ds.uuid,))
    rpt.add_attribute(Attribute(Constants.A_INSTRUMENT,
                                d_bam[Constants.A_INSTRUMENT]))
    rpt.add_attribute(Attribute(Constants.A_COVERAGE,
                                d_var[Constants.A_COVERAGE]))
    rpt.add_attribute(Attribute(Constants.A_CONCORDANCE,
                                d_var[Constants.A_CONCORDANCE]))
    rpt.add_attribute(Attribute(Constants.A_READLENGTH,
                                d_map[Constants.A_READLENGTH]))
    rpt.add_attribute(Attribute(Constants.A_READS, d_bam[Constants.A_READS]))
    rpt = spec.apply_view(rpt)
    rpt.write_json(os.path.join(output_dir, report))


def _validate_inputs(files):
    """
    Raise an Error if a required file is null or non-existent
    :param files: list of tuples, first element of tuple is input name second is value
    """
    for f in files:
        if f[1] is None:
            raise PbReportError('{f} cannot be None'.format(f=f[0]))
        if not os.path.exists(f[1]):
            raise IOError('{f} does not exist'.format(f=f[1]))


def _cell_2_inst(cell):
    try:
        chunks = cell.split('_')
        # Original:
        if len(chunks) == 4:
            return chunks[2]
        # Timestamped:
        if len(chunks) == 3:
            return chunks[0][1:]
    except:
        #raise ValueError('Invalid cell {c}'.format(c=cell))
        return "Unknown"


def _get_variants_data(variants_rpt_file):
    """
    Extract attributes from the variants report.
    :param variants_rpt_file: (str) path to the variants report
    :return dict: coverage and concordance
    """
    rpt = load_report_from_json(variants_rpt_file)
    coverage = rpt.get_attribute_by_id(Constants.V_COVERAGE).value
    concordance = rpt.get_attribute_by_id(Constants.V_CONCORDANCE).value
    return {Constants.A_COVERAGE: coverage, Constants.A_CONCORDANCE: concordance}


def _get_mapping_stats_data(mapping_stats_rpt_file):
    """
    Extract attributes from the mapping stats report.
    :param mapping_stats_rpt_file: (str) path to the mapping stats report
    :return dict: mean mapped read length
    """
    rpt = load_report_from_json(mapping_stats_rpt_file)
    rl = rpt.get_attribute_by_id(Constants.M_READLENGTH).value
    return {Constants.M_READLENGTH: rl}


def _get_read_hole_data(reads_by_cell, instrument):
    """
    Process the dictionary of hole data.
    :param reads_by_cell_then_set: (dict) _get_reads_info
    """
    if len(reads_by_cell) == 0:
        return {
            Constants.A_INSTRUMENT: instrument,
            "reads_set_1": 0,
            Constants.A_READS: 0
        }
        #raise ValueError("NO CELLS found!")
    yield_, yield_1 = None, None

    cell = reads_by_cell.keys()[0]
    reads = reads_by_cell[cell]

    if '1' in reads:
        yield_1 = len(reads['1'])

    yield_ = len(reads)
    d = {}
    d[Constants.A_INSTRUMENT] = instrument
    d['reads_set_1'] = yield_1
    d[Constants.A_READS] = yield_
    return d


def _get_reads_info(aligned_reads_file):
    """
    Extract information from the BAM files. Returns a tuple of length 2.
    First item is a dictionary of dictionaries, such that holes are mapped by cell, then set.
    Second item is the instrument name. 
    :param aligned_reads_file: (str) path to aligned_reads[.xml,.bam]
    :return tuple (reads_by_cell_then_set, instrument) (dict, string): A dictionary of dictionaries,
    instrument name
    """
    instruments = set()
    reads_by_cell = defaultdict(set)
    with AlignmentSet(aligned_reads_file) as ds:
        for bamfile in ds.resourceReaders():
            for rg in bamfile.readGroupTable:
                cell = movie_to_cell(rg.MovieName)
                instruments.add(_cell_2_inst(cell))
            if ds.isIndexed:
                logging.info("Indexed file - will use fast loop.")
                for (hole, rgId) in zip(bamfile.holeNumber, bamfile.qId):
                    movie_name = bamfile.readGroupInfo(rgId).MovieName
                    cell = movie_to_cell(movie_name)
                    reads_by_cell[cell].add(hole)
            else:
                for aln in bamfile:
                    hole = aln.HoleNumber
                    movie_name = aln.movieName
                    cell = movie_to_cell(movie_name)
                    if inst is None:
                        inst = _cell_2_inst(cell)
                    reads_by_cell[cell].add(hole)
    return reads_by_cell, ", ".join(sorted(list(instruments)))


def summarize_report(report_file, out=sys.stdout):
    report = load_report_from_json(report_file)
    attr = {a.id: a for a in report.attributes}
    coverage = attr[Constants.A_COVERAGE]
    concordance = attr[Constants.A_CONCORDANCE]
    out.write("{f}:\n".format(f=report_file))
    out.write("  {n}: {v}\n".format(n=concordance.name, v=concordance.value))
    out.write("  {n}: {v}\n".format(n=coverage.name, v=coverage.value))
    return coverage.value == 1 and concordance.value == 1


def args_runner(args):
    make_sat_report(
        aligned_reads_file=args.alignment_file,
        mapping_stats_report=args.mapping_stats_rpt,
        variants_report=args.var_rpt,
        report=args.report,
        output_dir=args.output)
    return 0


def resolved_tool_contract_runner(resolved_tool_contract):
    report_file = resolved_tool_contract.task.output_files[0]
    make_sat_report(
        aligned_reads_file=resolved_tool_contract.task.input_files[0],
        mapping_stats_report=resolved_tool_contract.task.input_files[2],
        variants_report=resolved_tool_contract.task.input_files[1],
        report=os.path.basename(report_file),
        output_dir=os.path.dirname(report_file))
    return 0


def _add_options_to_parser(p):
    desc = spec.description
    p = add_base_options_pbcommand(p, spec.title)
    p.add_input_file_type(FileTypes.DS_ALIGN,
                          file_id="alignment_file",
                          name="AlignmentSet",
                          description="AlignmentSet XML or aligned .bam file")
    p.add_input_file_type(FileTypes.REPORT,
                          file_id="var_rpt",
                          name="Variant report JSON",
                          description="The variants report - i.e., variants_report.json")
    p.add_input_file_type(FileTypes.REPORT,
                          file_id="mapping_stats_rpt",
                          name="Mapping statistics JSON",
                          description="The mapping statistics report - i.e., "
                          "mapping_stats_report.json")
    return p


def _get_parser_core():
    p = get_pbparser(
        Constants.TOOL_ID,
        __version__,
        spec.title,
        __doc__,
        Constants.DRIVER_EXE,
        is_distributed=True)
    return p


def get_parser():
    p = _get_parser_core()
    _add_options_to_parser(p)
    return p


def main(argv=sys.argv):
    mp = get_parser()
    return pbparser_runner(argv[1:],
                           mp,
                           args_runner,
                           resolved_tool_contract_runner,
                           log,
                           setup_log)

# for 'python -m pbreports.report.sat ...'
if __name__ == "__main__":
    sys.exit(main())
