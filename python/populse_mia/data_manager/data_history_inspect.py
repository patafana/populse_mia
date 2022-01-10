# -*- coding: utf-8 -*- #
"""
"""

from populse_mia.data_manager.project import (BRICK_EXEC, BRICK_EXEC_TIME,
                                              BRICK_INIT, BRICK_INIT_TIME,
                                              BRICK_INPUTS, BRICK_NAME,
                                              BRICK_OUTPUTS, COLLECTION_BRICK,
                                              COLLECTION_CURRENT,
                                              COLLECTION_INITIAL, TAG_BRICKS,
                                              TAG_CHECKSUM, TAG_EXP_TYPE,
                                              TAG_FILENAME, TAG_TYPE, TYPE_MAT,
                                              TYPE_NII, TYPE_TXT, TYPE_UNKNOWN)
from capsul.api import capsul_engine, Process, Pipeline
import traits.api as traits
import os.path as osp


def data_history_pipeline(filename, project):
    """
    """
    procs, links = get_data_history_processes(filename, project)

    if procs:
        pipeline = Pipeline()
        for proc in procs.values():
            name = proc.name
            if name in pipeline.nodes:
                name = '%s_%s' % (proc.name, proc.uuid)
            proc.node_name = name
            pipeline.add_process(name, proc)

        for link in links:
            if link[0] is None:
                src = link[1]
                if src not in pipeline.traits():
                    pipeline.export_parameter(link[2].node_name, link[3], src)
                    src = None
            else:
                src = '%s.%s' % (link[0].node_name, link[1])
            if link[2] is None:
                dst = link[3]
                if dst not in pipeline.traits():
                    pipeline.export_parameter(link[0].node_name, link[1], dst)
                    dst = None
            else:
                dst = '%s.%s' % (link[2].node_name, link[3])
            if src is not None and dst is not None:
                pipeline.add_link('%s->%s' % (src, dst))

        return pipeline

    else:
        return None


def get_direct_proc_ancestors(filename, project, procs):
    session = project.session
    bricks = session.get_value(COLLECTION_CURRENT, filename, TAG_BRICKS)
    print('bricks for:', filename, ':', bricks)

    new_procs = {}
    new_links = set()

    if bricks is not None:
        for brick in bricks:
            if brick not in procs:
                proc = get_history_brick_process(brick, project)
                if proc is None:
                    continue

                procs[brick] = proc
                new_procs[brick] = proc
            else:
                new_procs[brick] = procs[brick]

    return new_procs


def get_data_history_processes(filename, project):
    session = project.session

    procs = {}
    links = set()
    new_procs = get_direct_proc_ancestors(filename, project, procs)
    done_procs = set()

    todo = list(new_procs.values())

    while todo:
        proc = todo.pop(0)
        done_procs.add(proc)

        print('-- ancestors for:', proc.uuid, proc.name)
        values_w_files = {}
        for name in proc.user_traits():
            trait = proc.trait(name)
            if not trait.output:
                value = getattr(proc, name)
                filenames = get_filenames_in_value(value, project)
                # record inputs referencing files in the DB
                if filenames:
                    print(name, 'will be parsed.')
                    values_w_files[name] = (value, filenames)

        for name, (value, filenames) in values_w_files.items():
            for nfilename in filenames:
                prev_procs = get_direct_proc_ancestors(nfilename, project,
                                                       procs)

                n_procs = [pproc for pproc in prev_procs.values()
                           if pproc not in done_procs]
                todo += n_procs

                # connect outputs of prev_procs which are identical to
                print('look for value', value, 'in', prev_procs.keys())
                for pproc in prev_procs.values():
                    print('- in', pproc.name)
                    for pname in pproc.user_traits():
                        ptrait = pproc.trait(pname)
                        if ptrait.output:
                            print(pname, 'is an output')
                            pval = getattr(pproc, pname, project)
                            if pval == value \
                                    or data_in_value(pval, nfilename, project):
                                links.add((pproc, pname, proc, name))

                if len(n_procs) == 0:
                    links.add((None, name, proc, name))

        for proc in new_procs.values():
            for name in proc.user_traits():
                trait = proc.trait(name)
                if trait.output:
                    value = getattr(proc, name)
                    if data_in_value(value, filename, project):
                        links.add((proc, name, None, name))

    return procs, links


def data_in_value(value, filename, project):
    if isinstance(value, str):
        proj_dir = osp.join(osp.abspath(osp.normpath(project.folder)), '')
        return value == osp.join(proj_dir, filename)
    if isinstance(value, (list, tuple)):
        for val in value:
            if data_in_value(val, filename, project):
                return True
        return False
    if hasattr(value, 'values'):
        for val in value.values():
            if data_in_value(val, filename, project):
                return True
    return False


def is_data_entry(filename, project):
    proj_dir = osp.join(osp.abspath(osp.normpath(project.folder)), '')
    if not filename.startswith(proj_dir):
        return None
    filename = filename[len(proj_dir):]
    if project.session.has_document(COLLECTION_CURRENT, filename):
        return filename
    return None


def get_filenames_in_value(value, project):
    values = [value]
    filenames = set()
    while values:
        value = values.pop(0)
        if isinstance(value, str):
            nvalue = is_data_entry(value, project)
            if nvalue:
                filenames.add(nvalue)
        elif isinstance(value, (list, tuple)):
            values.extend(value)
        elif hasattr(value, 'values'):
            values.extend(value.values())

    return filenames


def get_history_brick_process(brick_id, project):
    """
    """

    session = project.session
    binfo = session.get_document(COLLECTION_BRICK, brick_id)
    print(brick_id, ':', binfo[BRICK_NAME])
    print(binfo.keys())
    inputs = binfo[BRICK_INPUTS]
    #print('inputs:', inputs)
    outputs = binfo[BRICK_OUTPUTS]
    #print('outputs:', outputs)
    exec_status = binfo[BRICK_EXEC]
    print('exec:', exec_status)
    if exec_status != 'Done':
        return None

    proc = Process()
    proc.name = binfo[BRICK_NAME].split('.')[-1]
    proc.uuid = brick_id

    for name, value in inputs.items():
        proc.add_trait(name, traits.Any(output=False))
        setattr(proc, name, value)

    for name, value in outputs.items():
        proc.add_trait(name, traits.Any(output=True))
        setattr(proc, name, value)

    return proc

