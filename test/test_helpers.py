#!/usr/bin/env python
# Copyright 2018 ARC Centre of Excellence for Climate Extremes
# author: Paola Petrelli <paola.petrelli@utas.edu.au>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from clef.helpers import check_values, load_vocabularies, check_keys, get_version, time_axis, \
                         get_keys, fix_model, fix_path, get_range, convert_periods, ids_dict
from clef.exception import ClefException
                          
from code_fixtures import c5_kwargs, c5_vocab, c5_keys, nranges, periods, empty, dids6, dids5, \
                          results5, results6
import pytest

# Tests for the functions defined in code.py

def test_check_values(c5_kwargs, c5_vocab):
    assert check_values(c5_kwargs, 'CMIP5', c5_vocab) is True
    bad_arg=c5_kwargs.copy()
    bad_arg['experiment'] = 'dummy'
    with pytest.raises(ClefException):
        check_values(bad_arg, 'CMIP5', c5_vocab)

def test_check_load_vocabularies():
    project = 'CMIP5'
    vocab = load_vocabularies(project)
    assert 'variables' in vocab.keys()
    assert 'stypes' not in vocab.keys()

    project = 'CMIP6'
    vocab = load_vocabularies(project)
    assert 'variables' in vocab.keys()
    assert 'families' not in vocab.keys()


def test_check_keys(c5_kwargs,c5_keys):
    args = check_keys(c5_keys, c5_kwargs)
    assert args == {'model': 'INM-CM4', 'experiment': 'rcp85', 'variable': 'tas',
                    'cmor_table': 'Amon', 'time_frequency': 'mon', 'institute': 'MIROC',
                    'experiment_family': 'RCP', 'ensemble': 'r1i1p1'}
    bad_arg=c5_kwargs.copy()
    bad_arg['activity_id'] = 'dummy'
    with pytest.raises(ClefException):
        args = check_keys(c5_keys, bad_arg)


def test_get_keys():
    with pytest.raises(ClefException):
        get_keys('dummy')


def test_fix_model():
    models = fix_model('cmip5', ['INM-CM4'], invert=True)
    assert models == ['inmcm4']
    arg_model = ['CESM1-BGC', 'ACCESS1-0']
    models = fix_model('CMIP5', arg_model)
    assert models == ['CESM1(BGC)', 'ACCESS1.0']


def test_convert_periods(nranges, periods, empty):
    res1 = convert_periods(nranges)
    assert res1 == periods[0]
    assert convert_periods(empty) == ([])

    nranges2 = nranges.copy()
    nranges2.append(None)
    res2 = convert_periods(nranges2)
    assert res2 == res1

def test_time_axis(periods):
    #test contiguos axis monthly frequency
    assert time_axis(periods[0],'20060101','21001231') is True
    #test contiguos axis, 2 files, daily frequency
    bad_list=periods[0][0:2]
    assert time_axis(bad_list,'20050101','20050228') is False

def test_get_range(periods, empty):
    assert get_range(periods[0]) == ('20060101', '21001231')
    assert get_range(empty) == (None, None)

def test_fix_path():
    dir1 = '/g/data/rr3/publications/CMIP5/output1/CSIRO-BOM/more/files/tas_20120115/'
    dir2 = '/g/data/rr3/publications/CMIP5/output1/CSIRO-QCCCE/more/files/tas_20110518/'
    dir3 = '/g/data/al33/replicas/CMIP5/output1/more/v20120316/tas/'
    dir4 =  dir3.replace('output1', 'unsolicited')
    dir5 = '/g/data1/rr3/publications/CMIP5/output1/CSIRO-BOM/more/files/pr_20141119/'
    fname = 'name.nc'
    latest=True
    assert fix_path(dir1, latest) == '/g/data/rr3/publications/CMIP5/output1/CSIRO-BOM/more/latest/tas/'
    assert fix_path(dir1+fname, latest) == '/g/data/rr3/publications/CMIP5/output1/CSIRO-BOM/more/latest/tas/name.nc'
    assert fix_path(dir2, latest) == '/g/data/rr3/publications/CMIP5/output1/CSIRO-QCCCE/more/files/tas_20110518/'
    assert fix_path(dir3, latest) == '/g/data/al33/replicas/CMIP5/combined/more/v20120316/tas/'
    assert fix_path(dir3+fname, latest) == '/g/data/al33/replicas/CMIP5/combined/more/v20120316/tas/name.nc'
    assert fix_path(dir4, latest) == '/g/data/al33/replicas/CMIP5/combined/more/v20120316/tas/'
    assert fix_path(dir5, latest) == '/g/data1/rr3/publications/CMIP5/output1/CSIRO-BOM/more/latest/pr/'
    latest=False
    assert fix_path(dir5, latest) == '/g/data1/rr3/publications/CMIP5/output1/CSIRO-BOM/more/files/pr_20141119/'


def test_get_version():
    assert get_version('/g/data/inst/model/var/v20130405') == '20130405'
    assert get_version('/g/data/inst/model/var/v20130405/tas/files') == '20130405'
    assert get_version('/g/data/inst/model/var/files/tas_20110518') == '20110518'
    assert get_version('/g/data/inst/model/var/noversionhere/tas/files') == None


def test_ids_dict(dids6, results6, dids5, results5):
    assert ids_dict(dids6) == results6
    assert ids_dict(dids5) == results5