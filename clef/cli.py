#!/usr/bin/env python
# Copyright 2017 ARC Centre of Excellence for Climate Systems Science
# author: Scott Wales <scott.wales@unimelb.edu.au>
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
from __future__ import print_function
from .db import connect, Session
from .model import Path, C5Dataset, C6Dataset, ExtendedMetadata, Checksum
from .esgf import match_query, find_local_path, find_missing_id, find_checksum_id
from .request import *
from .exception import ClefException
import click
import logging
from sqlalchemy import any_, or_
from sqlalchemy.orm import aliased
import sys
import six
import os
import json
import pkg_resources

def clef_catch():
    try:
        clef()
    except ClefException as e:
        click.echo('ERROR: %s'%e)
        sys.exit(1)


@click.group()
@click.option('--remote', 'flow', is_flag=True, default=False, flag_value='remote', 
               help="returns only ESGF search results")
@click.option('--local', 'flow', is_flag=True, default=False, flag_value='local', 
               help="returns only local files matching ESGF search")

@click.option('--missing', 'flow', is_flag=True, default=False, flag_value='missing',
               help="returns only missing files matching ESGF search")
@click.option('--request', 'flow', is_flag=True, default=False, flag_value='request',
               help="send NCI request to download missing files matching ESGF search")
@click.pass_context
def clef(ctx, flow):
    ctx.obj={}
    ctx.obj['flow'] = flow
    

def warning(message):
    print("WARNING: %s"%message, file=sys.stderr)

def load_vocabularies(project):
    vfile = pkg_resources.resource_filename(__name__, 'data/'+project+'_validation.json')
    with open(vfile, 'r') as f:
         data = f.read()
         models = json.loads(data)['models'] 
         realms = json.loads(data)['realms'] 
         variables = json.loads(data)['variables'] 
         frequencies = json.loads(data)['frequencies'] 
         tables = json.loads(data)['tables'] 
         #experiments = json.loads(data)['experiments'] 
         if project == 'CMIP6':
             activities = json.loads(data)['activities'] 
             stypes = json.loads(data)['source_types'] 
             return models, realms, variables, frequencies, tables, activities, stypes
    return models, realms, variables, frequencies, tables 
    

def cmip5_args(f):
    models, realms, variables, frequencies, tables = load_vocabularies('CMIP5')
    constraints = [
        click.option('--experiment', '-e', multiple=True, help="CMIP5 experiment: piControl, rcp85, amip ..."),
        click.option('--experiment_family',multiple=True, help="CMIP5 experiment family: Decadal, RCP ..."),
        click.option('--model', '-m', multiple=True, type=click.Choice(models),  metavar='x', 
                      help="CMIP5 model acronym: ACCESS1.3, MIROC5 ..."),
        click.option('--table', '--mip', '-t', 'cmor_table', multiple=True, type=click.Choice(tables) ),
                      #help="CMIP5 CMOR table: Amon, day, Omon ..."),
        click.option('--variable', '-v', multiple=True, type=click.Choice(variables), metavar='x',
                      help="Variable name as shown in filanames: tas, pr, sic ... "),
        click.option('--ensemble', '--member', '-en', 'ensemble', multiple=True, help="CMIP5 ensemble member: r#i#p#"),
        click.option('--frequency', 'time_frequency', multiple=True, type=click.Choice(frequencies) ), 
                     # help="Frequency"),
        click.option('--realm', multiple=True, type=click.Choice(realms) ),
                     # help="CMIP5 realm"),
        click.option('--institution', 'institute', multiple=True, help="Modelling group institution id: MIROC, IPSL, MRI ...")
    ]
    for c in reversed(constraints):
        f = c(f)
    return f

def common_args(f):
    constraints = [
        click.argument('query', nargs=-1),
        click.option('--cf_standard_name',multiple=True, help="CF variable standard_name, use instead of variable constraint "),
        click.option('--format', 'oformat', type=click.Choice(['file','dataset']), default='dataset',
                     help="Return output for datasets (default) or individual files"),
        click.option('--latest/--all-versions', 'latest', default=True,  
                     help="Return only the latest version or all of them. Default: --latest"),
        click.option('--replica/--no-replica', default=False, 
                     help="Return both original files and replicas. Default: --no-replica"),
        click.option('--distrib/--no-distrib', 'distrib', default=True, 
                     help="Distribute search across all ESGF nodes. Default: --distrib"),
        click.option('--debug/--no-debug', default=False,
                     help="Show debug output. Default: --no-debug")
    ]
    for c in reversed(constraints):
        f = c(f)
    return f

def cmip6_args(f):
# 
    models, realms, variables, frequencies, tables, activities, stypes = load_vocabularies('CMIP6')
    constraints = [
        click.option('--activity', '-mip', 'activity_id', multiple=True, type=click.Choice(activities) ) ,
                     #help="CMIP6 MIP or project id"),
        click.option('--experiment', '-e', 'experiment_id', multiple=True, help="CMIP6 experiment, list of available depends on activity"),
        click.option('--source_type',multiple=True, type=click.Choice(stypes) ),
                     #help="Model configuration"),
        click.option('--table', '-t', 'table_id', multiple=True, type=click.Choice(tables), metavar='x',
                     help="CMIP6 CMOR table: Amon, SIday, Oday ..."),
        click.option('--model', '--source_id','-m', 'source_id', multiple=True, type=click.Choice(models),  metavar='x',
                     help="CMIP6 model id: GFDL-AM4, CNRM-CM6-1 ..."),
        click.option('--variable', 'variable_id', '-v', multiple=True, type=click.Choice(variables),  metavar='x', 
                     help="CMIP6 variable name as in filenames"),
        click.option('--member', '-mi', 'member_id', multiple=True, help="CMIP6 member id: <sub-exp-id>-r#i#p#f#"),
        click.option('--grid', '--grid_label', '-g', 'grid_label', multiple=True, help="CMIP6 grid label: i.e. gn for the model native grid"),
        click.option('--resolution', '--nominal_resolution','-nr' , 'nominal_resolution', multiple=True, help="Approximate resolution: '250 km', pass in quotes"),
        click.option('--frequency',multiple=True, type=click.Choice(frequencies) ),
                     # help="Frequency"),
        click.option('--realm', multiple=True, type=click.Choice(realms) ),
                     # help="CMIP6 realm"),
        click.option('--sub_experiment_id', '-se', multiple=True, help="Only available for hindcast and forecast experiments: sYYYY"),
        click.option('--variant_label', '-vl', multiple=True, help="Indicates a model variant: r#i#p#f#"),
        click.option('--institution', 'institution_id', multiple=True, help="Modelling group institution id: IPSL, NOAA-GFDL ..."),
    ]
    for c in reversed(constraints):
        f = c(f)
    return f


@clef.command()
@cmip5_args
@common_args
@click.pass_context
def cmip5(ctx, query, debug, distrib, replica, latest, oformat,
        cf_standard_name,
        ensemble,
        experiment,
        experiment_family,
        institute,
        cmor_table,
        model,
        realm,
        time_frequency,
        variable,
        ):
    """
    Search local database for files matching the given constraints

    Constraints can be specified multiple times, in which case they are combined    using OR: -v tas -v tasmin will return anything matching variable = 'tas' or variable = 'tasmin'.
    The --latest flag will check ESGF for the latest version available, this is the default behaviour
    """

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger('sqlalchemy.engine').setLevel(level=logging.INFO)

    #user=os.environ['USER']
    user=None
    connect(user=user)
    s = Session()

    project='CMIP5'

    ensemble_terms = None
    model_terms = None

    dataset_constraints = {
        'ensemble': ensemble,
        'experiment': experiment,
        'institute': institute,
        'model': model,
        'realm': realm,
        'time_frequency': time_frequency,
        'cmor_table': cmor_table,
        'variable': variable
        }


    #if ctx.obj['flow'] == 'request':
    #    print('Sorry! This option is not yet implemented')
    #    return

    if ctx.obj['flow'] == 'remote':
        q = find_checksum_id(' '.join(query),
            distrib=distrib,
            replica=replica,
            latest=latest,
            cf_standard_name=cf_standard_name,
            ensemble=ensemble,
            experiment=experiment,
            experiment_family=experiment_family,
            institute=institute,
            cmor_table=cmor_table,
            model=model,
            project=project,
            realm=realm,
            time_frequency=time_frequency,
            variable=variable
            )

        if oformat == 'file':
            for result in s.query(q):
                print(result.id)
        else:
            ids=set(x.dataset_id for x in s.query(q))
            for did in ids:
                print(did)
              
        return

    terms = {}

    for key, value in six.iteritems(dataset_constraints):
        if len(value) > 0:
           terms[key] = value

    subq = match_query(s, query=' '.join(query),
            distrib= distrib,
            replica=replica,
            latest=(None if latest == 'all' else latest),
            cf_standard_name=cf_standard_name,
            experiment_family=experiment_family,
            project=project,
            **terms
            )

    ql = find_local_path(s, subq, oformat=oformat)
    if not ctx.obj['flow'] == 'missing':
        for result in ql:
            print(result[0])
    if ctx.obj['flow'] == 'local': 
        return

    qm = find_missing_id(s, subq, oformat=oformat)

    # if there are missing datasets, search for dataset_id in synda queue, update list and print result 
    if qm.count() > 0:
        updated = search_queue(qm, project)
        print('\nAvailable on ESGF but not locally:')
        for result in updated:
            print(result)
    else:
        print('\nEverything available on ESGF is also available locally')

    if ctx.obj['flow'] == 'request':
        if len(updated) >0:
            write_request('CMIP5',updated)
        else:
            print("\nAll the published data is already available locally, or has been requested, nothing to request")


@clef.command()
@cmip6_args
@common_args
@click.pass_context
def cmip6(ctx,query, debug, distrib, replica, latest, oformat,
        cf_standard_name,
        variant_label,
        member_id,
        experiment_id,
        sub_experiment_id,
        source_type,
        institution_id,
        table_id,
        source_id,
        realm,
        frequency,
        variable_id,
        activity_id,
        grid_label,
        nominal_resolution
        ):
    """
    Search local database for files matching the given constraints

    Constraints can be specified multiple times, in which case they are combined    using OR: -v tas -v tasmin will return anything matching variable = 'tas' or variable = 'tasmin'.
    The --latest flag will check ESGF for the latest version available, this is the default behaviour
    """

    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger('sqlalchemy.engine').setLevel(level=logging.INFO)

    #user=os.environ['USER']
    user=None
    connect(user=user)
    s = Session()

    project='CMIP6'

    ensemble_terms = None
    model_terms = None

    dataset_constraints = {
        'member_id': member_id,
        'activity_id': activity_id,
        'experiment_id': experiment_id,
        'sub_experiment_id': sub_experiment_id,
        'institution_id': institution_id,
        'source_id': source_id,
        'source_type': source_type,
        'realm': realm,
        'frequency': frequency,
        'table_id': table_id,
        'variable_id': variable_id,
        'grid_label': grid_label,
        'nominal_resolution': nominal_resolution
        }

    #if ctx.obj['flow'] == 'request':
    #    print('Sorry! This option is not yet implemented')
        #return

    if ctx.obj['flow'] == 'remote':
        q = find_checksum_id(' '.join(query),
            distrib=distrib,
            replica=replica,
            latest=latest,
            cf_standard_name=cf_standard_name,
            variant_label=variant_label,
            member_id=member_id,
            experiment_id=experiment_id,
            source_type=source_type,
            institution_id=institution_id,
            table_id=table_id,
            source_id=source_id,
            project=project,
            realm=realm,
            frequency=frequency,
            variable_id=variable_id,
            activity_id=activity_id,
            grid_label=grid_label,
            nominal_resolution=nominal_resolution
            )

        if oformat == 'file':
            for result in s.query(q):
                print(result.id)
        else:
            ids=set(x.dataset_id for x in s.query(q))
            for did in ids:
                print(did)
        return

    terms = {}

    # Add filters
    for key, value in six.iteritems(dataset_constraints):
        if len(value) > 0:
            terms[key] = value

    subq = match_query(s, query=' '.join(query),
            distrib=distrib,
            replica=replica,
            latest=(None if latest == 'all' else latest),
            cf_standard_name=cf_standard_name,
            project=project,
            **terms
            )

    ql = find_local_path(s, subq, oformat=oformat)
    if not ctx.obj['flow'] == 'missing':
        for result in ql:
            print(result[0])
    if ctx.obj['flow'] == 'local': 
        return

    qm = find_missing_id(s, subq, oformat=oformat)
    
    # if there are missing datasets, search for dataset_id in synda queue, update list and print result 
    if qm.count() > 0:
        updated = search_queue(qm, project)
        print('\nAvailable on ESGF but not locally:')
        for result in updated:
            print(result)
    else:
        print('\nEverything available on ESGF is also available locally')

    if ctx.obj['flow'] == 'request':
        if len(updated) >0:
            write_request(project,updated)
        else:
            print("\nAll the published data is already available locally, or has been requested, nothing to request")
