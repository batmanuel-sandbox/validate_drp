from __future__ import division, print_function, absolute_import

import os

from lsst.pipe.base import CmdLineTask, ArgumentParser, TaskRunner
from lsst.pex.config import Config, Field
from lsst.meas.base.forcedPhotCcd import PerTractCcdDataIdContainer
from lsst.utils import getPackageDir
from lsst.validate.base import load_metrics
from .validate import runOneFilter, plot_metrics


class MatchedVisitMetricsRunner(TaskRunner):
    """Subclass of TaskRunner for MatchedVisitMetrics

    This class transforms the processed
    arguments generated by the ArgumentParser into the arguments expected by
    MatchedVisitMetricsTask.run().
    """

    @staticmethod
    def getTargetList(parsedCmd, **kwargs):
        # organize data IDs by filter
        idListDict = {}
        for ref in parsedCmd.id.refList:
            idListDict.setdefault(ref.dataId["filter"], []).append(ref.dataId)
        # we call run() once with each filter
        return [(parsedCmd.butler,
                 filterName,
                 parsedCmd.output,
                 idListDict[filterName],
                 ) for filterName in sorted(idListDict.keys())]

    def __call__(self, args):
        task = self.TaskClass(config=self.config, log=self.log)
        return task.run(*args)


class MatchedVisitMetricsConfig(Config):
    outputPrefix = Field(
        dtype=str, default="matchedVisit",
        doc="Root name for output files: the filter name is appended to this+'_'."
    )
    metricsFile = Field(
        dtype=str, optional=True,
        doc="Full path to metrics file, or None to use metrics in validate_drp."
    )
    brightSnr = Field(
        dtype=float, default=100,
        doc="Minimum PSF signal-to-noise ratio for a star to be considered bright."
    )
    safeSnr = Field(
        dtype=float, default=50,
        doc="Minimum median PSF signal-to-noise ratio for a match to be considered safe."
    )
    makeJson = Field(
        dtype=bool, default=True,
        doc="Whether to write JSON outputs."
    )
    makePlots = Field(
        dtype=bool, default=True,
        doc="Whether to write plot outputs."
    )
    matchRadius = Field(
        dtype=float, default=1.0,
        doc="Match radius (arcseconds)."
    )
    useJointCal = Field(
        dtype=bool, default=False,
        doc="Whether to use jointcal (or meas_mosaic) to calibrate measurements"
    )
    skipTEx = Field(
        dtype=bool, default=False,
        doc="Skip TEx calculations (useful for older catalogs that don't have PsfShape measurements)."
    )
    verbose = Field(
        dtype=bool, default=False,
        doc="More verbose output during validate calculations."
    )


class MatchedVisitMetricsTask(CmdLineTask):
    """An alternate command-line driver for the validate_drp metrics.

    MatchedVisitMetricsTask is very much an incomplete CmdLineTask - it uses
    the usual mechanisms to define its inputs and read them using a Butler,
    but writes outputs manually to files with a configuration-defined prefix
    (config.outputPrefix).  Because the CmdLineTask machinery always creates an
    output Butler repository, however, it is necessary to run this task with
    both an output directory and an output prefix, with the former essentially
    unused.

    The input data IDs passed via the `--id` argument should contain the same
    keys as the `wcs` dataset (those used by the `calexp` dataset plus
    `tract`).  When `config.useJointCal` is `True`, the `photoCalib` and `wcs`
    datasets are used to calibrate sources; when it is `False`, `tract` is
    ignored (but must still be present) and the photometric calibration is
    retrieved from the `calexp` and the sky positions of sources are loaded
    directly from the `src` dataset (which is used to obtain raw measurmenets
    in both cases).
    """

    _DefaultName = "matchedVisitMetrics"
    ConfigClass = MatchedVisitMetricsConfig
    RunnerClass = MatchedVisitMetricsRunner

    def __init__(self, **kwds):
        CmdLineTask.__init__(self, **kwds)
        metricsFile = self.config.metricsFile
        if metricsFile is None:
            metricsFile = os.path.join(getPackageDir('validate_drp'), 'etc', 'metrics.yaml')
        self.metrics = load_metrics(metricsFile)

    def run(self, butler, filterName, output, dataIds):
        """
        Compute cross-visit metrics for one filter.

        Parameters
        ----------
        butler      The initialized butler.
        filterName  The filter name to be processed.
        output      The output repository to save files to.
        dataIds     The butler dataIds to process.
        """
        outputPrefix = os.path.join(output, "%s_%s"%(self.config.outputPrefix, filterName))
        job = runOneFilter(butler, dataIds, metrics=self.metrics,
                           brightSnr=self.config.brightSnr,
                           safeMaxExtended=self.config.safeMaxExtended,
                           makeJson=self.config.makeJson,
                           filterName=filterName,
                           outputPrefix=outputPrefix,
                           useJointCal=self.config.useJointCal,
                           skipTEx=self.config.skipTEx,
                           verbose=self.config.verbose)
        if self.config.makePlots:
            plot_metrics(job, filterName, outputPrefix=outputPrefix)

    @classmethod
    def _makeArgumentParser(cls):
        parser = ArgumentParser(name=cls._DefaultName)
        parser.add_id_argument("--id", "wcs", help="data ID, with raw CCD keys + tract",
                               ContainerClass=PerTractCcdDataIdContainer)
        return parser

    def _getConfigName(self):
        return None

    def _getMetadataName(self):
        return None
