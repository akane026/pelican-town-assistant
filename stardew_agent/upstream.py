"""Execute selected unmodified function ASTs, avoiding upstream model-loading imports.

This is component-level execution only, not full mKG-RAG reproduction. Source is
the pinned Apache-2.0 author repository, retained locally without modifications.
"""
import ast, asyncio, html, os, re
from collections import defaultdict
from typing import Any
import numpy as np
from PIL import Image
from .core import *

BASE=ROOT/'third_party/mkg-rag-e9cc3f5'
def components():
    ns={'__builtins__':__builtins__,'Any':Any,'html':html,'re':re,'os':os,'np':np,'Image':Image,'defaultdict':defaultdict}
    requested={
      'rag/multimodal/utils.py':['clean_str'],
      'rag/utils.py':['is_float_regex'],
      'rag/multimodal/operate.py':['format_scene_graph','load_roi_image'],
      'rag/multimodal/build.py':['_handle_single_entity_extraction','_handle_single_relationship_extraction','_handle_single_mapping_extraction','_handle_images_attribute']}
    hashes={}
    for path,names in requested.items():
        text=(BASE/path).read_text(encoding='utf-8');tree=ast.parse(text)
        definitions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
        if {n.name for n in definitions}!=set(names):raise ValidationError('UPSTREAM_COMPONENT_MISSING')
        module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]+definitions,type_ignores=[])
        exec(compile(ast.fix_missing_locations(module),str(BASE/path),'exec'),ns)
        hashes[path]=file_hash(BASE/path)
    return ns,hashes

def run_reference(build_id):
    g=read(ARTIFACTS/'builds'/build_id/'fused_graph.json');ns,hashes=components()
    obs=next(o for o in g['observations'] if o['method']=='ChatECNU_visual/v1')
    asset=next(a for a in g['assets'] if a['id']==obs['asset_id'])
    aligned=next(a for a in g['alignments'] if a['observation_id']==obs['id'] and a['target_kind']=='entity')
    entity=next(n for n in g['entities'] if n['id']==aligned['target_id'])
    scene={'objects':[{'id':i,'category':o['visible_description'],'bbox':o['bbox_normalized_xyxy']} for i,o in enumerate(obs['objects'])],'relations':[]}
    formatted=ns['format_scene_graph'](scene);rois=ns['load_roi_image'](str(ROOT/asset['path']),[o['bbox'] for o in scene['objects']])
    name=entity['name'];source=g['evidence'][0]['id']
    async def execute():
        e=await ns['_handle_single_entity_extraction'](['"entity"',name,entity['type'],name],source)
        # Mapping is from a real pipeline alignment. It is not an independent gold label.
        m=await ns['_handle_single_mapping_extraction'](['"mapping"','image',name,'1.0'],source)
        n={e['entity_name']:[e]};edges={}
        await ns['_handle_images_attribute']([m],n,edges,image_dir=str(ROOT),image_path=str(ROOT/asset['path']),scene_graph=scene,global_config={})
        return n,m
    n,m=asyncio.run(execute())
    result={'status':'PASS_COMPONENT_EXECUTION','classification':'original_function_bodies_via_import_isolation',
        'commit':'e9cc3f5728bb8cf1d3904614532a7345db0f0f47','source_hashes':hashes,'input_origin':'real_MLLM_observation_and_real_pipeline_alignment',
        'scene_graph':scene,'formatted':formatted,'roi_shapes':[list(r.shape) for r in rois],'mapping':m,'fused_nodes':n,
        'limitations':['Not full original extract_entities orchestration.','Mapping prediction came from domain adapter; original mapping parser and image fusion ran.',
                      'Original endpoint-only relation matching and whole-image fallback are not adopted in production.','No EGTR/QM loaded.']}
    write(ARTIFACTS/'upstream/component_run.json',result);return result
