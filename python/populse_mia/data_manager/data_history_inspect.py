# -*- coding: utf-8 -*- #
"""
"""

from populse_mia.data_manager.project import (BRICK_EXEC, BRICK_EXEC_TIME,
                                              BRICK_INIT, BRICK_INIT_TIME,
                                              BRICK_INPUTS, BRICK_NAME,
                                              BRICK_ID,
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
            if getattr(proc, 'used', False):
                name = proc.name
                if name in pipeline.nodes:
                    name = '%s_%s' % (proc.name, proc.uuid.replace('-', '_'))
                proc.node_name = name
                pipeline.add_process(name, proc)

        for link in links:
            if link[0] is None:
                src = link[1]
                if src not in pipeline.traits():
                    pipeline.export_parameter(link[2].node_name, link[3], src)
                    src = None
                elif pipeline.trait(src).output:
                    # already taken as an output: export under another name
                    done = False
                    n = 0
                    while not done:
                        src2 = '%s_%d' % (src, n)
                        if src2 not in pipeline.traits():
                            pipeline.export_parameter(
                                link[2].node_name, link[3], src2)
                            src = None
                            done = True
                        elif not pipeline.trait(src2).output:
                            src = src2
                            done = True
                        n += 1
            else:
                src = '%s.%s' % (link[0].node_name, link[1])
            if link[2] is None:
                dst = link[3]
                if dst not in pipeline.traits():
                    pipeline.export_parameter(link[0].node_name, link[1], dst)
                    dst = None
                elif not pipeline.trait(dst).output:
                    # already taken as an input: export under another name
                    done = False
                    n = 0
                    while not done:
                        dst2 = '%s_%d' % (dst, n)
                        if dst2 not in pipeline.traits():
                            pipeline.export_parameter(
                                link[0].node_name, link[1], dst2)
                            dst = None
                            done = True
                        elif pipeline.trait(dst2).output:
                            dst = dst2
                            done = True
                        n += 1
            else:
                dst = '%s.%s' % (link[2].node_name, link[3])
            if src is not None and dst is not None:
                try:
                    pipeline.add_link('%s->%s' % (src, dst))
                except ValueError as e:
                    print(e)

        return pipeline

    else:
        return None


def get_direct_proc_ancestors(filename, project, procs, before_exec_time=None,
                              only_oldest=True, org_proc=None):
    session = project.session
    bricks = session.get_value(COLLECTION_CURRENT, filename, TAG_BRICKS)
    print('bricks for:', filename, ':', bricks)

    new_procs = {}
    new_links = set()

    if bricks is not None:
        for brick in bricks:
            if brick not in procs:
                proc = get_history_brick_process(
                    brick, project, before_exec_time=before_exec_time)
                if proc is None:
                    continue

                procs[brick] = proc
                new_procs[brick] = proc
            else:
                proc = procs[brick]
                if before_exec_time and proc.exec_time > before_exec_time:
                    continue
                new_procs[brick] = procs[brick]

    if only_oldest:
        # keep last run(s)
        later_date = None
        keep_procs = {}
        for uuid, proc in new_procs.items():
            if org_proc and proc is org_proc:
                # ignore origin proc for date sorting
                continue
            date = proc.exec_time
            if later_date is None:
                later_date = date
                keep_procs[uuid] = proc
            elif date > later_date:
                later_date = date
                keep_procs = {uuid: proc}
            elif date == later_date:
                # ambiguity: keep all equivalent
                keep_procs[uuid] = proc
            else:
                print('drop earlier run:', proc.name, uuid)
        if org_proc and org_proc.uuid in new_procs:
            # set back origin process, if it's in the list
            keep_procs[org_proc.uuid] = org_proc
    else:
        keep_procs = new_procs

    return keep_procs


def get_proc_ancestors_via_tmp(proc, project, procs):
    '''
    Try to get upstream process(es) for proc, connected via a temp value
    ("<temp>").

    For this, try to match processes in the output files history bricks
    '''
    new_procs = {}
    links = set()
    dlink = None
    tmp_filename = '<temp>'

    def _get_tmp_param(proc):
        for param, trait in proc.user_traits().items():
            if not trait.output:
                value = getattr(proc, param)
                if data_in_value(value, tmp_filename, project):
                    return (proc, param)
        return (None, None)  # failed...

    # look first from proc outputs history (which is more direct, less error-
    # prone, and a more limited search)
    for name, trait in proc.user_traits().items():
        if trait.output:
            value = getattr(proc, name)
            filenames = get_filenames_in_value(value, project,
                                               allow_temp=False)
            for filename in filenames:
                hprocs = get_direct_proc_ancestors(
                    filename, project, procs, before_exec_time=proc.exec_time,
                    only_oldest=False)
                if proc.uuid in hprocs:
                    # exclude the current proc
                    del hprocs[proc.uuid]
                sprocs = find_procs_with_output(hprocs.values(), tmp_filename,
                                                project)
                for exec_time in sorted(sprocs, reverse=True):
                    for hproc, param in sprocs[exec_time]:
                        new_procs[hproc.uuid] = hproc
                        if dlink is None:
                            dlink = _get_tmp_param(proc)
                        links.add((hproc, param, dlink[0], dlink[1]))
                        # we have found a link (starting with the older): stop
                        break
                    if len(new_procs) != 0:
                        break
                # if found, should we still process other filenames ?

    if len(new_procs) == 0:
        # not found in data history: search the entire bricks histories
        session = project.session
        print('temp history not found from output filenames...')

        #print('test bricks older than:', proc.exec_time)
        # filtering for date <= doesn't seem to work as I expect...
        #bricks = session.filter_documents(
            #COLLECTION_BRICK, '{%s} <= "%s"' % (BRICK_EXEC_TIME, proc.exec_time))
        candidates = {}
        bricks = session.get_documents(COLLECTION_BRICK)
        for brick in bricks:
            #if brick
            if brick[BRICK_EXEC] != 'Done':
                continue
            if brick[BRICK_EXEC_TIME] > proc.exec_time:
                continue
            #print('try brick:', brick[BRICK_NAME])
            outputs = brick[BRICK_OUTPUTS]
            for name, value in outputs.items():
                if data_in_value(value, tmp_filename, project):
                    candidates.setdefault(brick[BRICK_EXEC_TIME], []).append(
                        (brick, name))
                    #print('CANDIDATE.')
                    break
        for exec_time in sorted(candidates, reverse=True):
            for brick, name in candidates[exec_time]:
                brick_id = brick[BRICK_ID]
                hproc = procs.get(brick_id)
                if hproc is None:
                    hproc = get_history_brick_process(brick_id, project)
                    procs[brick_id] = hproc
                new_procs[brick_id] = hproc
                if dlink is None:
                    dlink = _get_tmp_param(proc)
                links.add((hproc, name, dlink[0], dlink[1]))
                print('found:', hproc.name, name)
                break
            break

    return new_procs, links


def find_procs_with_output(procs, filename, project):
    '''
    Returns
    -------
    sprocs: dict
        exec_time: [(process, param_name), ...]
    '''
    sprocs = {}
    for proc in procs:
        for name, trait in proc.user_traits().items():
            if trait.output:
                value = getattr(proc, name)
                if data_in_value(value, filename, project):
                    sprocs.setdefault(proc.exec_time, []).append((proc, name))
    return sprocs


def get_data_history_processes(filename, project):
    session = project.session

    procs = {}
    links = set()
    new_procs = get_direct_proc_ancestors(filename, project, procs)
    done_procs = set()

    # keep only the latest to begin with
    later_date = None
    keep_procs = {}
    for uuid, proc in new_procs.items():
        date = proc.exec_time
        if later_date is None:
            later_date = date
            keep_procs[uuid] = proc
        elif date > later_date:
            later_date = date
            keep_procs = {uuid: proc}
        elif date == later_date:
            # ambiguity: keep all equivalent
            keep_proc[uuid] = proc
        else:
            print('drop earlier run:', proc.name, uuid)

    todo = list(keep_procs.values())

    while todo:
        proc = todo.pop(0)
        if proc in done_procs:
            continue
        done_procs.add(proc)
        proc.used = True

        print('-- ancestors for:', proc.uuid, proc.name, proc.exec_time)
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
                if nfilename == '<temp>':
                    print('temp file used -- history is broken')
                    prev_procs, prev_links = get_proc_ancestors_via_tmp(
                        proc, project, procs)
                    links.update(prev_links)

                    n_procs = [pproc for pproc in prev_procs.values()
                              if pproc not in done_procs]
                    todo += n_procs
                else:
                    prev_procs = get_direct_proc_ancestors(
                        nfilename, project, procs,
                        before_exec_time=proc.exec_time, org_proc=proc)

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
                                        or data_in_value(pval, nfilename,
                                                         project):
                                    links.add((pproc, pname, proc, name))

                if len(prev_procs) == 0 or prev_procs == {proc.uuid: proc}:
                    # the param has no previous processing or just the current
                    # self-modifing process: connect it to main inputs
                    links.add((None, name, proc, name))

    for proc in keep_procs.values():
        for name in proc.user_traits():
            trait = proc.trait(name)
            if trait.output:
                value = getattr(proc, name)
                if data_in_value(value, filename, project):
                    links.add((proc, name, None, name))

    return procs, links


def data_in_value(value, filename, project):
    if isinstance(value, str):
        if filename != '<temp>':
            proj_dir = osp.join(osp.abspath(osp.normpath(project.folder)), '')
            filename = osp.join(proj_dir, filename)
        return value == filename
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


def is_data_entry(filename, project, allow_temp=True):
    if allow_temp and filename == '<temp>':
        return filename
    proj_dir = osp.join(osp.abspath(osp.normpath(project.folder)), '')
    if not filename.startswith(proj_dir):
        return None
    filename = filename[len(proj_dir):]
    if project.session.has_document(COLLECTION_CURRENT, filename):
        return filename
    return None


def get_filenames_in_value(value, project, allow_temp=True):
    values = [value]
    filenames = set()
    while values:
        value = values.pop(0)
        if isinstance(value, str):
            nvalue = is_data_entry(value, project, allow_temp=allow_temp)
            if nvalue:
                filenames.add(nvalue)
        elif isinstance(value, (list, tuple)):
            values.extend(value)
        elif hasattr(value, 'values'):
            values.extend(value.values())

    return filenames


def get_history_brick_process(brick_id, project, before_exec_time=None):
    """
    """

    session = project.session
    binfo = session.get_document(COLLECTION_BRICK, brick_id)
    if binfo is None:
        return None
    #print(brick_id, ':', binfo[BRICK_NAME])
    #print(binfo.keys())
    inputs = binfo[BRICK_INPUTS]
    outputs = binfo[BRICK_OUTPUTS]
    exec_status = binfo[BRICK_EXEC]
    #print('exec:', exec_status)
    if exec_status != 'Done':
        return None
    exec_time = binfo[BRICK_EXEC_TIME]
    print(brick_id, 'exec_time:', type(exec_time), exec_time, ', before:', before_exec_time)
    if before_exec_time and exec_time > before_exec_time:
        # ignore later runs
        return None
    print(brick_id, ':', binfo[BRICK_NAME])

    proc = Process()
    proc.name = binfo[BRICK_NAME].split('.')[-1]
    proc.uuid = brick_id
    proc.exec_time = exec_time

    for name, value in inputs.items():
        proc.add_trait(name, traits.Any(output=False, optional=True))
        setattr(proc, name, value)

    for name, value in outputs.items():
        proc.add_trait(name, traits.Any(output=True, optional=True))
        setattr(proc, name, value)

    return proc

