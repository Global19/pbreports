#!/usr/bin/env python

"""
Generates a report showing a table of top variants sorted by confidence.
"""

import logging
import os
import sys

from pbcommand.models.report import Table, Column, Report, PbReportError
from pbcommand.models import FileTypes, get_pbparser
from pbcommand.cli import pbparser_runner
from pbcommand.utils import setup_log
from pbcore.io import GffReader, ReferenceSet

from pbreports.util import openReference
from pbreports.io.specs import *

log = logging.getLogger(__name__)

__version__ = '0.1'


class Constants(object):
    R_ID = "topvariants"
    TOOL_ID = "pbreports.tasks.top_variants"
    DRIVER_EXE = "python -m pbreports.report.top_variants --resolved-tool-contract"
    HOW_MANY_ID = "pbreports.task_options.how_many"
    BATCH_SORT_SIZE_ID = "pbreports.task_options.batch_sort_size"
    HOW_MANY_DEFAULT = 100
    BATCH_SORT_SIZE_DEFAULT = 10000
    C_SEQ = 'sequence'
    C_POS = 'position'
    C_VAR = 'variant'
    C_TYP = 'type'
    C_COV = 'coverage'
    C_CON = 'confidence'
    C_FRE = 'frequency'
    C_GEN = 'genotype'
    T_TOP = "top_variants_table"

spec = load_spec(Constants.R_ID)


def make_topvariants_report(gff, reference, how_many, batch_sort_size, report,
                            output_dir):
    """
    Entry to report.
    :param gff: (str) path to variants.gff (or rare_variants.gff). Note, could also be *.gz
    :param reference: (str) path to reference dir
    :param how_many: (int)
    :param batch_sort_size: (int)
    :param report: (str) report name
    :param batch_sort_size: (str) output dir
    """
    _validate_inputs(gff, reference, how_many, batch_sort_size)

    table_builder = VariantTableBuilder()
    vf = VariantFinder(gff, reference, how_many, batch_sort_size)
    top = vf.find_top()
    for v in top:
        table_builder.add_variant(v)

    r = Report(Constants.R_ID, tables=[table_builder.table],
               dataset_uuids=(ReferenceSet(reference).uuid,))
    r = spec.apply_view(r)
    r.write_json(os.path.join(output_dir, report))
    return 0


def _validate_inputs(gff, reference, how_many, batch_sort_size):
    """
    Raise an Error if a required file is null or non-existent
    :param gff: (str) path to variants.gff
    :param reference: (str) path to reference dir
    :param how_many: (int)
    :param batch_sort_size: (int)
    """
    if gff is None:
        raise PbReportError('gff cannot be None')
    if not os.path.exists(gff):
        raise IOError('gff {g} does not exist: '.format(g=gff))
    if reference is None:
        raise PbReportError('reference cannot be None')
    if not os.path.exists(reference):
        raise IOError('reference {g} does not exist: '.format(g=reference))

    try:
        int(how_many)
    except:
        raise ValueError('how_many = {h}. int required.')

    try:
        int(batch_sort_size)
    except:
        raise ValueError('batch_sort_size = {h}. int required.')


class BaseVariantTableBuilder(object):

    def __init__(self):
        cols = []
        cols.append(Column(Constants.C_SEQ))
        cols.append(Column(Constants.C_POS))
        cols.append(Column(Constants.C_VAR))
        cols.append(Column(Constants.C_TYP))
        cols.append(Column(Constants.C_COV))
        cols.append(Column(Constants.C_CON))

        log.debug('# columns {n}'.format(n=len(cols)))

        self._table = Table(self._get_table_id(), title=self._get_table_title(),
                            columns=cols)

    def _get_table_title(self):
        pass

    def _get_table_id(self):
        pass

    @property
    def table(self):
        """
        :returns: Table
        """
        return self._table

    def _add_common_variant_atts(self, variant):
        """
        Add variant attributes common to the top variant report.
        :param variant: Variant
        """
        self._table.add_data_by_column_id(Constants.C_SEQ, variant.contig)
        self._table.add_data_by_column_id(Constants.C_POS, variant.position)
        self._table.add_data_by_column_id(Constants.C_VAR, variant.variant)
        self._table.add_data_by_column_id(Constants.C_TYP, variant.type)
        self._table.add_data_by_column_id(Constants.C_COV, variant.coverage)
        self._table.add_data_by_column_id(Constants.C_CON, variant.confidence)


class VariantTableBuilder(BaseVariantTableBuilder):

    def __init__(self):
        super(VariantTableBuilder, self).__init__()
        self._table.columns.append(Column(Constants.C_GEN, ''))

    def _get_table_title(self):
        return ""

    def _get_table_id(self):
        return Constants.T_TOP

    def add_variant(self, variant):
        self._add_common_variant_atts(variant)
        self._table.add_data_by_column_id(Constants.C_GEN, variant.genotype)


class VariantFinder(object):

    def __init__(self, variantsGff, referenceDir, howMany=100, batchSortSize=10000):
        """varianstGff = source file, which can be a .gz; howMany = top N variants;
        batchSortSize = the size of intermediate lists we sort.
        referenceDir = referenceRepository dir, so we can fetch real contig names"""
        self._howMany = howMany
        self._batchSortSize = batchSortSize
        self._variantsGff = variantsGff
        self._rezip = False
        self._reference = openReference(referenceDir)

    def find_top(self):
        """Sorting strategy here is to sort sublists and truncate down to list size as
        we go. So, for a 10000 line file, 1000 batchSortSize, and 100 final (howMany),
        iterate through the file, and sort each 1000 chunk, take the top 100"""

        reader = None

        with GffReader(self._variantsGff) as reader:

            locallist = []
            count = 0

            for gff3Record in reader:

                if count == self._batchSortSize:
                    locallist = self._sortAndTrim(locallist)
                    count = 0

                locallist.append(Variant(gff3Record))
                count = count + 1
            if count == 0:
                return []

            finalList = self._sortAndTrim(locallist)
            self._addContigNames(finalList)

            return finalList

    def _addContigNames(self, list):
        """Add reference repos contig names to the top variants"""

        for v in list:
            # top variants are initialized with contig == seqid
            ctig = self._reference.get_contig(v.contig)
            if ctig == None:
                continue
            v.contig = ctig.id

    def _sortAndTrim(self, list):
        """Sort this chunk and trim it down to the final list size"""
        s = sorted(list, key=lambda variant: variant.confidence, reverse=True)
        if(len(s) > self._howMany):
            return s[:self._howMany]
        return s


# label attributes
INS = "INS"
DEL = "DEL"
SUB = "SUB"


class Variant(object):

    def __init__(self, gff3Record):
        """Attribute object for rendering in a table"""

        self.position = long(gff3Record.start)
        self.type = self._getTypeStr(gff3Record.type)

        # by default, assign internal id to the variant
        self.contig = gff3Record.seqid.split()[0]

#        recDict = self._toDictionary(gff3Record._getAttributeString() )
        self.coverage = int(gff3Record.attributes['coverage'])
        self.confidence = float(gff3Record.attributes['confidence'])
        self.length = int(gff3Record.attributes.get('length', 1))

        if gff3Record.attributes.has_key('variantSeq'):
            self.variantSeq = gff3Record.attributes['variantSeq']

        if gff3Record.attributes.has_key('genotype'):
            self.genotype = gff3Record.attributes['genotype']
        else:
            self.genotype = 'haploid'

        if gff3Record.attributes.has_key('frequency'):
            self.frequency = gff3Record.attributes['frequency']

        if "reference" in gff3Record.attributes:
            self.reference = gff3Record.attributes['reference']

        # do this last, since it depends on other fields
        self.variant = self._createVariant()

    def _createVariant(self):
        """See: http://hgvs.org/mutnomen"""

        if(self.type == INS):
            pos = "%i_%i" % (self.position, self.position + 1)
            return "".join([pos, "ins", self.variantSeq])

        if(self.type == DEL):
            return "".join([str(self.position), "del", self.reference])

        if(self.type == SUB):
            return "".join([str(self.position), self.reference, ">", self.variantSeq])

    def _getTypeStr(self, variant_type):
        variant_types = {'insertion': INS,
                         'deletion': DEL,
                         'substitution': SUB}
        if variant_type in variant_types:
            return variant_types[variant_type]
        else:
            raise KeyError("Unsupported variant type {x}. Supported types {t}".format(
                x=variant_type, t=variant_types.keys()))

    def _toDictionary(self, attributeString):
        """convert an attribute line to a dictionary"""
        return dict(item.split("=") for item in attributeString.split(";"))


def _get_parser():
    p = get_pbparser(
        Constants.TOOL_ID,
        __version__,
        spec.title,
        __doc__,
        Constants.DRIVER_EXE,
        is_distributed=True)
    p.add_output_file_type(FileTypes.REPORT, "report", "Top Variants Report",
                           description="Summary of top 100 variants",
                           default_name="top_variants_report")
    p.add_input_file_type(FileTypes.GFF,
                          file_id="gff",
                          name="GFF file",
                          description="variants.gff (can be gzip'ed)")
    p.add_input_file_type(FileTypes.DS_REF,
                          file_id="reference",
                          name="Reference dataset",
                          description="ReferenceSet or FASTA")
    # p.add_output_file_type(FileTypes.REPORT, "report",
    #                       "JSON report", "JSON report", "report.json")
    p.add_int(Constants.HOW_MANY_ID, "how_many",
              default=Constants.HOW_MANY_DEFAULT,
              name="Number of variants",
              description="number of top variants to show (default=100)")
    p.add_int(Constants.BATCH_SORT_SIZE_ID, "batch_sort_size",
              default=Constants.BATCH_SORT_SIZE_DEFAULT,
              name="Batch sort size",
              description="Intermediate sort size parameter (default=10000)")
    return p


def _args_runner(args):
    return make_topvariants_report(
        gff=args.gff,
        reference=args.reference,
        how_many=args.how_many,
        batch_sort_size=args.batch_sort_size,
        report=args.report,
        output_dir=os.path.dirname(args.report))


def _resolved_tool_contract_runner(rtc):
    return make_topvariants_report(
        gff=rtc.task.input_files[0],
        reference=rtc.task.input_files[1],
        how_many=rtc.task.options[Constants.HOW_MANY_ID],
        batch_sort_size=rtc.task.options[Constants.BATCH_SORT_SIZE_ID],
        report=rtc.task.output_files[0],
        output_dir=os.path.dirname(rtc.task.output_files[0]))


def main(argv=sys.argv):
    return pbparser_runner(argv[1:],
                           _get_parser(),
                           _args_runner,
                           _resolved_tool_contract_runner,
                           log,
                           setup_log)


if __name__ == "__main__":
    sys.exit(main())
