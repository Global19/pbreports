#!/usr/bin/env python
import os
import logging

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from pbcommand.models.report import Plot

log = logging.getLogger(__name__)


def get_fig_axes_lpr(dims=(8, 6), facecolor='#ffffff', gridcolor='#e0e0e0'):
    """
    Get a matplotlib figure object, with lpr-themed face and gridcolors.
    This theme is white background, gray gridlines, and .5 alpha.
    """
    fig, ax = get_fig_axes(dims, facecolor, gridcolor)
    fig.patch.set_alpha(0.5)
    ax.patch.set_alpha(0.5)
    return fig, ax


def get_fig_axes(dims=(8, 6), facecolor='#e0e0e0', gridcolor='#ffffff'):
    """
    Get a matplotlib figure object.
    This theme is background (default=gray) and grid lines (default=white).
    """
    fig = plt.figure(figsize=dims)
    fig.patch.set_alpha(0.5)
    ax = fig.add_subplot(111)
    ax.axesPatch.set_facecolor(facecolor)
    ax.grid(color=gridcolor, linewidth=0.5, linestyle='-')
    ax.set_axisbelow(True)
    return fig, ax


class Line(object):

    """
    Defines a line for consumption by apply_line_data: array data + style information
    """

    def __init__(self, xData, yData, style='-', color='#a6cee3', width=1.0):
        self.xData = xData
        self.yData = yData
        self.style = style
        self.color = color
        self.width = width


class LineFill(Line):

    """
    Defines a line and fill information. Filling is +/- in the Y-direction at each point.
    Default fill is light red
    """

    def __init__(self, xData, yData, yDataMin, yDataMax, style='-', linecolor='#a6cee3',
                 linewidth=1.0, alpha=0.6, edgecolor='#f05050', facecolor='#f05050'):
        """
        alpha (float) describes filling
        """
        Line.__init__(self, xData, yData, style, linecolor, linewidth)
        self.yDataMin = yDataMin
        self.yDataMax = yDataMax
        self.alpha = alpha
        self.edgecolor = edgecolor
        self.facecolor = facecolor


class Bar(object):

    """Defines a bar chart category"""

    def __init__(self, data, label, color='#a6cee3'):
        self.data = data
        self.color = color
        self.label = label


def get_bar_plot_legend_fig(bars, figsize=(2, 2)):
    fig, ax = get_fig_axes_lpr(dims=figsize)
    barMeta = []
    for barModel in bars:
        # nonsense bar with bogus values - all we want is the color
        aBar = ax.bar([1], [1], color=barModel.color,
                      edgecolor=barModel.color)[0]
        barMeta.append((aBar, barModel.label))

    fig.legend([bar[0] for bar in barMeta], [bar[1]
                                             for bar in barMeta], loc=10, frameon=False)
    return fig


def apply_line_fill_data(ax, line_fill_models):
    """
    Apply line "fill between" to a line plot.
    Typically, you'd call apply_line_data to generate your primary line(s) and axes ticks.
    Then call this function to fill between a min/max for each point in your line.

    Arguments:\n
    axes - required param, see get_fig_axes()\n
    line_models - array of LineFill objects to plot \n
    """
    for line_f in line_fill_models:
        ax.fill_between(line_f.xData, line_f.yDataMin, line_f.yDataMax,
                        where=None, alpha=line_f.alpha, edgecolor=line_f.edgecolor,
                        facecolor=line_f.facecolor)


def apply_line_data(ax, line_models,
                    axis_labels=('', ''),
                    xlim=None, ylim=None,
                    only_whole_ticks=True):
    """
    Apply line plot data to axes.

    Arguments:\n
    axes - required param, see get_fig_axes()\n
    line_models - array of Line objects to plot \n
    xlim, ylim - tuple axis limits
    only_whole_ticks - deprecate?

    """

    for line in line_models:
        ax.plot(line.xData, line.yData, line.style,
                color=line.color, linewidth=line.width)

    ax.set_xlabel(axis_labels[0])
    ax.set_ylabel(axis_labels[1])

    # AAK see if this is fixed with newer numpy
    #  with six or greater points it's always wholeNumberTicks in my experience and sometimes breaks -AAK
    # if onlyWholeNumberTicks and reduce(lambda x,y: x and len(y.xData) < 6, lineModels, True):
    #    setOnlyWholeNumberXticks(ax)

    if ylim:
        ax.set_ylim(ylim)
    if xlim:
        ax.set_xlim(xlim)


def apply_bar_data(ax, bars, labels, axis_labels=('', ''), data_file=None):

    def y_height_sort(i, j):
        """Basically a sorting comparator for rectangles"""
        if j.get_height() > i.get_height():
            return 1
        else:
            return -1

    for barModel in bars:
        ax.bar(labels, barModel.data, color=barModel.color,
               edgecolor=barModel.color)

    # Here, we reorder the N bars PER X position. They must be rendered so highest is in back,
    # shorter bars are in the foreground
    allPatches = ax.patches
    xPatches = {}
    for p in allPatches:
        if p.get_x() not in xPatches:
            xPatches[p.get_x()] = []
        xPatches[p.get_x()].append(p)

    for xPos, patches in xPatches.iteritems():
        if len(patches) == 1:
            continue
        patches.sort(cmp=y_height_sort)
        [patch.set_zorder(patches.index(patch)) for patch in patches]

    # Only show 5 lables on the x axis. Each label divisable by 1000
    maxX = labels[len(labels) - 1]
    step = int(maxX * 0.2)

    # hacky way to get a step divisable by 1000.

    for i in range(1001):
        step = step + 1
        if (step) % 1000 == 0:
            break

    # For contigs < 1000 bases, readjust the x-axis so we see ticks
    if maxX < 1000:
        step = 100

    ax.set_xticks(np.arange(0, maxX, step))

    ax.set_xlabel(axis_labels[0])
    ax.set_ylabel(axis_labels[1])

    # requirement for variants plot is to show int vals on
    # the y-axis, not floats.
    formatter = ticker.FuncFormatter(_intAxisFormatter)
    ax.yaxis.set_major_formatter(formatter)


def _intAxisFormatter(val, pos):
    """2-argument function you can pass to FuncFormatter to customize axes. In this case,
    if val is an int, return a string representation of it. Else, return empty string. """
    try:
        if int(val) == val:
            return str(val)
        return ''

    except:
        return ''


def apply_histogram_data(ax, data, bins, axis_labels=('', ''),
                         barcolor='#226F96',
                         xlim=None, ylim=None,
                         xmin=None, ymin=None,
                         showEdges=True, log_scale=False, title=None,
                         weights=None,
                         data_file=None):
    """
    Apply histogram data to axes.
        The default barcolor is steel blue

    Arguments:\n
    axes - required param, see get_fig_axes()\n
    data - data array to plot\n
    bins - int - how many data bins\n

    data_file - pass in a file name to which to write tab-delimited chart data
        (for debugging purposes)
    """
    edgeColor = '#ffffff'

    if not showEdges:
        edgeColor = barcolor

    if len(data) > 0:
        if not isinstance(data, np.ndarray):
            data = np.array(data)
        dtype = np.result_type(data)
        if "int" in dtype.type.__name__ and len(np.unique(data)) > 1:
            d = min(np.diff(np.unique(data)))
            left_of_first_bin = min(data) - float(d) / 2
            right_of_last_bin = max(data) + float(d) / 2
            ax.hist(data, np.arange(left_of_first_bin, right_of_last_bin + d, d),
                    ec=edgeColor, fc=barcolor, log=log_scale, weights=weights)
        else:
            ax.hist(data, bins=bins, ec=edgeColor, fc=barcolor, log=log_scale,
                    weights=weights)
    else:
        # Perhaps this should be an exception.
        log.warn("Empty dataset. Unable to generate histogram.")

    ax.set_xlabel(axis_labels[0])
    ax.set_ylabel(axis_labels[1])

    if ylim:
        ax.set_ylim(ylim)
    if xlim:
        ax.set_xlim(xlim)

    if title is not None:
        ax.set_title(title)

    try:
        if data_file is not None:
            dump = ChartDataDump(data_file)
            dump.addData("data", data)
            dump.write()
    except Exception as err:
        log.error('Unable to dump chart data to {f}: {e}'.format(
            f=data_file, e=err))


def set_tick_label_font_size(ax, minor, major):
    """Convenience function for changing font size of major and minor ticks"""
    for tick in ax.xaxis.get_major_ticks() + ax.yaxis.get_major_ticks():
        tick.label1.set_fontsize(major)
    for tick in ax.xaxis.get_minor_ticks() + ax.yaxis.get_minor_ticks():
        tick.label1.set_fontsize(minor)


def set_axis_label_font_size(ax, size):
    """Convenience function for changing font size of x- and y-axis labels."""
    t = ax.get_xaxis().get_label()
    t.set_fontsize(size)
    t = ax.get_yaxis().get_label()
    t.set_fontsize(size)


def save_figure_with_thumbnail(figure, filename, dpi=60):
    """
    Convenience function to save a matplotlib figure object to 2 image files:
    A standard image and a thumbnail.

    Arguments:\n
    figure: a matplotlib figure object\n
    filename :  the name of the primary figure image file\n

    returns:
        - tuple (filename, thumbnail_filename)

    Example:
    save_standard_figures(figure, '/foo/myChart.png') -->
    /foo/myChart.png
    /foo/myChart_thumb.png

    returns a tuple of (basename of image, basename of thumbnail)
    """
    parts = os.path.splitext(filename)
    thumb = '{b}_thumb{e}'.format(b=parts[0], e=parts[1])
    _save_figures(figure, [(filename, dpi), (thumb, 20)])
    plt.close(figure)
    return filename, thumb


def _save_figures(figure, file_tuples):
    """
    Save a single matplotlib figure to one or more image files.
    Arguments:\n
    figure: a matplotlib figure object\n
    file_tuples :  a list of 2-tuples, filename and dpi
    """
    for fname, dpi in file_tuples:
        log.info('Saving figure {f} with dpi {d}'.format(f=fname, d=str(dpi)))
        figure.savefig(fname, dpi=dpi)


class ChartDataDump(object):

    """For debugging. Writes the data backing a chart to a tab file."""

    def __init__(self, fname):
        """
        fname - something like mychart.tsv
        """
        self.fname = fname
        self.dataMap = {}

    def addData(self, name, data):
        """Add named data list( such as xData ) to the dump object"""
        self.dataMap[name] = data

    def write(self):
        """Write the contents of the dump object to a file"""

        maxLen = 0
        out = open(self.fname, 'w')

        # HEADER
        for key in self.dataMap.keys():
            out.write(key)
            out.write('\t')
            length = len(self.dataMap[key])
            if length > maxLen:
                maxLen = length

        out.write('\n')

        # DATA
        for i in range(maxLen):
            for key in self.dataMap.keys():
                data = self.dataMap[key]
                if len(data) >= i:
                    out.write(str(data[i]))
                else:
                    out.write("-")
                out.write('\t')
            out.write('\n')

        out.close()

# Colors from filter stats/subreads reports

# blue-green tuples, arranged from darkest to lightest
_COLORS = [('#003E73', '#297900'),
           ('#0D5191', '#39910D'),
           ('#0E5FAB', '#42AB0E'),
           ('#578FC4', '#7BC457'),
           ('#8FB7DE', '#A9DE8F')]


def get_blue(shade):
    """Get a shaded of blue, where 0 is darkest and 4 is lightest"""
    return _COLORS[shade][0]


def get_green(shade):
    """Get a shaded of green, where 0 is darkest and 4 is lightest"""
    return _COLORS[shade][1]


def get_orange():
    """Counter-balancing orange color for variants bar charts"""
    return "#F18B17"


def make_histogram(datum, axis_labels, nbins, barcolor):
    """Create a fig, ax instance and generate a histogram.

    :param datum: np.array
    :param axis_labels: (tuple of str) (axis label, y axis label)
    :return: matplotlib fig, ax
    """
    fig, ax = get_fig_axes_lpr()
    apply_histogram_data(ax, datum, nbins, axis_labels=axis_labels,
                         barcolor=barcolor)
    return fig, ax


def make_histogram_with_cdf(datum, axis_labels, nbins, barcolor):
    """
    Make a histogram png file with cdf.
    """
    fig, ax = make_histogram(datum, axis_labels, nbins, barcolor)
    bins, bin_edges = np.histogram(datum, bins=nbins)
    bin_edges = np.array(bin_edges)
    rax = ax.twinx()
    log.debug("Min edges {e} bins {b}".format(e=len(bin_edges), b=len(bins)))
    csum = np.append([0], np.cumsum(bins)[:-1])
    sdf = [csum[-1] - i for i in csum]
    log.debug((len(bin_edges), len(sdf)))
    # Plot the data
    rax.plot(bin_edges[:-1], sdf, 'k')
    rax.set_xlim(bin_edges.min(), bin_edges.max())
    rax.set_ylim(ymin=0)
    if len(axis_labels) == 3:
        rax.set_ylabel(axis_labels[2])
    return fig, ax


def create_plot_impl(_make_plot_func, plot_id, axis_labels, nbins,
                     plot_name, barcolor, datum, output_dir, dpi=72):
    """Internal function used to create Plot instances.

    This should probably have a special container class to capture all the
    plot config options.
    """

    fig, _ax = _make_plot_func(datum, axis_labels, nbins, barcolor)
    path = os.path.join(output_dir, plot_name)
    try:
        fig.tight_layout()
    except AttributeError as e:  # FIXME bug 25872
        log.warn("figure.tight_layout() not available")
        log.warn(str(e))
    except ValueError as e:
        log.error(str(e))
    fig.savefig(path, dpi=dpi)
    log.debug("Saved plot with id {i} to {p}".format(p=path, i=plot_id))
    thumbnail = plot_name.replace(".png", "_thumb.png")

    fig.savefig(os.path.join(output_dir, thumbnail), dpi=20)
    plt.close(fig)
    log.debug("Saved plot to {p}".format(p=thumbnail))
    plot = Plot(plot_id, os.path.basename(plot_name),
                thumbnail=os.path.basename(thumbnail))
    return plot
