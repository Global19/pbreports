
"""
Generate XML report of adapter statistics.
"""

import functools
import logging
import os
import sys

import numpy as np

from pbreports.util import continuous_dist_shaper
from pbcommand.models.report import *
from pbcommand.cli import pbparser_runner
from pbcommand.utils import setup_log
from pbcore.io import SubreadSet

from pbreports.plot.helper import (get_fig_axes_lpr,
                                   save_figure_with_thumbnail, get_green)
from pbreports.model import InvalidStatsError
from pbreports.io.specs import *
from pbreports.util import (get_subreads_report_parser,
                            arg_runner_subreads_report,
                            rtc_runner_subreads_report)

__version__ = '0.1.0'


class Constants(object):
    TOOL_ID = "pbreports.tasks.adapter_report_xml"
    R_ID = "adapter_xml_report"
    DRIVER_EXE = ("python -m pbreports.report.adapter_xml "
                  "--resolved-tool-contract ")

    A_DIMERS = "adapter_dimers"
    A_SHORT_INSERTS = "short_inserts"
    A_BASE_RATE = "local_base_rate_median"

    PG_ADAPTER = "adapter_xml_plot_group"
    P_ADAPTER = "adapter_xml_plot"

    BASE_RATE_DIST = "LocalBaseRateDist"

log = logging.getLogger(__name__)
spec = load_spec(Constants.R_ID)


def to_report(stats_xml, output_dir, dpi=72):
    # TODO: make dpi matter
    """Main point of entry

    :type stats_xml: str
    :type output_dir: str
    :type dpi: int

    :rtype: Report
    """
    log.info("Analyzing XML {f}".format(f=stats_xml))
    dset = SubreadSet(stats_xml)
    if not dset.metadata.summaryStats:
        dset.loadStats(stats_xml)
    if not dset.metadata.summaryStats.medianInsertDists:
        raise InvalidStatsError("Pipeline Summary Stats (sts.xml) not found "
                                "or missing key distributions")

    # Pull some stats:
    adapter_dimers = np.round(
        100.0 * dset.metadata.summaryStats.adapterDimerFraction,
        decimals=2)
    short_inserts = np.round(
        100.0 * dset.metadata.summaryStats.shortInsertFraction,
        decimals=2)
    attributes = [Attribute(i, v) for i, v in
                  zip([Constants.A_DIMERS, Constants.A_SHORT_INSERTS],
                      [adapter_dimers, short_inserts])]

    if Constants.BASE_RATE_DIST in dset.metadata.summaryStats.tags:
        dist = dset.metadata.summaryStats[Constants.BASE_RATE_DIST]
        if len(dist) > 1:
            log.warn("Dataset was merged, local base rate not applicable")
        else:
            base_rate = dist[0].sampleMed
            attributes.append(Attribute(Constants.A_BASE_RATE, base_rate))
    else:
        log.warn("No local base rate distribution available")

    plots = []
    # Pull some histograms (may have dupes (unmergeable distributions)):
    shaper = continuous_dist_shaper(
        dset.metadata.summaryStats.medianInsertDists)
    for i, orig_ins_len_dist in enumerate(
            dset.metadata.summaryStats.medianInsertDists):
        ins_len_dist = shaper(orig_ins_len_dist)
        # make a bar chart:
        fig, ax = get_fig_axes_lpr()
        ax.bar(map(float, ins_len_dist.labels), ins_len_dist.bins,
               color=get_green(0), edgecolor=get_green(0),
               width=(ins_len_dist.binWidth * 0.75))
        ax.set_xlabel(get_plot_xlabel(spec, Constants.PG_ADAPTER,
                                      Constants.P_ADAPTER))
        ax.set_ylabel(get_plot_ylabel(spec, Constants.PG_ADAPTER,
                                      Constants.P_ADAPTER))
        png_fn = os.path.join(output_dir,
                              "interAdapterDist{i}.png".format(i=i))
        png_base, thumbnail_base = save_figure_with_thumbnail(fig, png_fn,
                                                              dpi=dpi)

        # build the report:
        plots.append(Plot("adapter_xml_plot_{i}".format(i=i),
                          os.path.relpath(png_base, output_dir),
                          thumbnail=os.path.relpath(thumbnail_base, output_dir)))

    plot_groups = [PlotGroup(Constants.PG_ADAPTER,
                             plots=plots,
                             thumbnail=os.path.relpath(thumbnail_base, output_dir))]
    tables = []

    report = Report(Constants.R_ID,
                    attributes=attributes,
                    tables=tables,
                    )  # plotgroups=plot_groups)

    return spec.apply_view(report)


resolved_tool_contract_runner = functools.partial(rtc_runner_subreads_report,
                                                  to_report)
args_runner = functools.partial(arg_runner_subreads_report, to_report)


def main(argv=sys.argv):
    mp = get_subreads_report_parser(Constants.TOOL_ID, __version__, spec.title,
                                    __doc__, Constants.DRIVER_EXE)
    return pbparser_runner(argv[1:],
                           mp,
                           args_runner,
                           resolved_tool_contract_runner,
                           log,
                           setup_log)

# for 'python -m pbreports.report.sat ...'
if __name__ == "__main__":
    sys.exit(main())
