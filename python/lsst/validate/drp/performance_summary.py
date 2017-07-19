# LSST Data Management System
# Copyright 2017 AURA/LSST.
#
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the LSST License Statement and
# the GNU General Public License along with this program.  If not,
# see <https://www.lsstcorp.org/LegalNotices/>.

from astropy.table import Column, Table

from lsst.validate.base import load_metrics
from lsst.validate.drp.validate import get_filter_name_from_job, load_json_output


def run(validation_drp_report_filenames, output_file,
        release_metrics_file=None, release_level=None):
    """
    Parameters
    ---
    validation_drp_report_filenames : [] or str giving filepaths for JSON files.
    output_file : str given filepath of output RST file.
    release_metrics_file : filepath of YAML file of a given release level.
       The JSON file will store the metrics it was calculated with
       But one will wish to compare against an external set of specifications.
       Such as the release for a given version during a given fiscal year.
    release_level : E.g., 'FY17' or 'ORR'
    """
    input_objects = ingest_data(validation_drp_report_filenames)
    input_table = objects_to_table(input_objects)
    if release_metrics_file is not None and release_level is not None:
        release_metrics = load_metrics(release_metrics_file)
        add_release_metric(input_table, release_metrics, release_level)

    write_report(input_table, output_file)


def ingest_data(filenames):
    """"""
    jobs = {}
    # Read in JSON output from metrics run
    for file in filenames:
        job = load_json_output(file)
        filter_name = get_filter_name_from_job(job)
        jobs[filter_name] = job

    return jobs


# Identify key data from JSON
def objects_to_table(input_objects, level='design'):
    """Take objects and convert to table."""
    rows = []
    for filter_name, obj in input_objects.items():
        for meas in obj.measurements:
            # Skip specification levels (called .name in measurement objects)
            #  that are not the 'level' we are looking for.
            if meas.spec_name is not None and meas.spec_name != level:
                continue
            m = meas.metric
            spec = m.get_spec(level, filter_name=filter_name)
            if meas.quantity is None:
                meas_quantity_value = "--"
            else:
                meas_quantity_value = meas.quantity.value
            this_row = [m.name, filter_name, meas_quantity_value, meas.unit,
                        m.operator_str, spec.quantity.value]
            rows.append(this_row)

    srd_requirement_col_name = 'SRD Requirement: %s' % level
    col_names = ('Metric', 'Filter', 'Value', 'Unit',
                 'Operator', srd_requirement_col_name)
    output = Table(rows=rows, names=col_names)
    output.add_column(Column(['']*len(output), dtype=str, name='Comments'))
    return output


# Calculate numbers in table
def add_release_metric(data, release_metrics, release_metrics_level):
    release_targets = []
    for row in data:
        metric = release_metrics[row['Metric']]
        spec = metric.get_spec(
            name=release_metrics_level, filter_name=row['Filter'])
        release_targets.append(spec.quantity.value)

    release_targets_col = Column(
        release_targets,
        dtype=float,
        name='Release Target: %s' % release_metrics_level)
    data.add_column(release_targets_col)

    return data


def float_or_dash(f, format_string='{:.2f}'):
    """Return string of formatted float, or -- if None."""
    # This try/except handles both None and non-numeric strings.
    try:
        return format_string.format(float(f))
    except:
        return '--'


def blank_none(s):
    if s is None:
        return ''
    if s == 'None':
        return ''

    return str(s)


def find_col_name(prefix, colnames):
    """Return the first entry in 'colnames' that starts with 'prefix'."""
    for c in colnames:
        if c.startswith(prefix):
            return c


# Output table
def write_report(data, filename='test.rst', format='ascii.rst'):
    # Find the 'Release Target XYZ' column name
    release_target_col_name = find_col_name('Release Target', data.colnames)
    # Find the 'SRD Requirement XYZ' column name
    srd_requirement_col_name = find_col_name('SRD Requirement', data.colnames)

    col_names = ['Metric', 'Filter', 'Unit', 'Operator',
                 srd_requirement_col_name,
                 release_target_col_name,
                 'Value', 'Comments']
    use_col_names = [c for c in col_names if c in data.colnames]
    # Provide default formats
    for spec_col in (release_target_col_name, srd_requirement_col_name):
        if spec_col in data:
            data[spec_col].info.format = '.1f'
    data['Value'].info.format = float_or_dash
    data['Unit'].info.format = blank_none
    data[use_col_names].write(filename=filename, format=format,
                              include_names=use_col_names,
                              overwrite=True)
