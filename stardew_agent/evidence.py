"""Server-created immutable, authenticated evidence values; no graph handles."""
from dataclasses import dataclass
import copy,hmac,secrets
from .core import *

def secret():
    p=DATA/'runtime/bundle.key';p.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
    except FileExistsError:pass
    return p.read_bytes()

@dataclass(frozen=True)
class VerifiedBundle:
    encoded:str
    signature:str
    def data(self):
        expected=hmac.new(secret(),self.encoded.encode(),'sha256').hexdigest()
        if not hmac.compare_digest(expected,self.signature):raise ValidationError('FORGED_EVIDENCE_BUNDLE')
        body=json.loads(self.encoded)
        evidence_ids={x['id'] for x in body['evidence_refs']}
        for record in body['facts']+body['relations']+body.get('alignments',[]):
            if not record.get('evidence_ids') or not set(record['evidence_ids'])<=evidence_ids:raise ValidationError('BUNDLE_SOURCE_MISSING')
        # No graph access: validate the exact source files already carried in the
        # authenticated bundle, including when it is passed directly to a rule.
        checked={}
        for e in body['evidence_refs']:
            path=contained(ROOT/e['raw_path']);key=str(path)
            if key not in checked:checked[key]=file_hash(path)
            if checked[key]!=e['source_sha256'] or digest(e['quote'].encode())!=e['quote_sha256']:raise ValidationError('BUNDLE_SOURCE_CHANGED')
        for asset in body.get('assets',[]):
            path=contained(ROOT/asset['path'])
            if file_hash(path)!=asset['sha256']:raise ValidationError('BUNDLE_IMAGE_CHANGED')
        return body

class BundleStore:
    def prepare(self,snapshot,fact_ids,relation_ids,entity_ids,*,task_id,revision,trace,supplements=(),candidate=False,alignment_ids=None,initial_retrieval_refs=None):
        """Pure preview for complete-payload budgeting; no signing or persistence."""
        def selected(kind,ids):
            try:return [copy.deepcopy(snapshot.records[kind][i]) for i in sorted(set(ids))]
            except KeyError as exc:raise ValidationError('UNKNOWN_EVIDENCE_ID') from exc
        facts=selected('facts',fact_ids);relations=selected('relations',relation_ids)
        if not candidate and snapshot.manifest.get('release_status')!='released':raise ValidationError('UNRELEASED_SNAPSHOT')
        if not candidate and any(not x.get('answer_allowed') or x.get('review_status')!='approved_human' for x in facts+relations):raise ValidationError('UNREVIEWED_EVIDENCE')
        nodes=set(entity_ids)|{f['subject'] for f in facts}|{r[e] for r in relations for e in ('subject','object')}
        entities=selected('entities',nodes)
        targets=set(fact_ids)|set(relation_ids)|nodes
        aligns=[copy.deepcopy(a) for a in snapshot.domain['alignments'] if a['target_id'] in targets and a['status']=='matched'
                and (alignment_ids is None or a['id'] in alignment_ids)
                and (candidate or (a.get('answer_allowed') and a.get('review_status')=='approved_human'))][:20]
        eids={e for r in facts+relations+aligns for e in r['evidence_ids']}
        evidence=selected('evidence',eids)
        regions=selected('regions',{r for a in aligns for r in a['region_ids']})
        assets=selected('assets',{r['asset_id'] for r in regions})
        body={'snapshot_id':snapshot.id,'task_id':task_id,'task_revision':revision,'facts':facts,'relations':relations,'entities':entities,
              'evidence_refs':evidence,'alignments':aligns,'regions':regions,'assets':assets,'selected_subgraph':{'node_ids':sorted(nodes),'relation_ids':sorted(set(relation_ids))},
              'initial_retrieval_refs':initial_retrieval_refs or [trace['trace_id']],'explicit_supplement_refs':list(supplements),'retrieval_trace':trace,
              'required_dependencies':[],'satisfied_dependencies':[],'missing_dependencies':[],
              'execution_mode':'candidate_diagnostic' if candidate else 'released','validation_status':'STRUCTURE_VALID_CANDIDATE' if candidate else 'VALIDATED'}
        body['bundle_id']='bundle:'+digest(body)
        return body
    def create(self,snapshot,fact_ids,relation_ids,entity_ids,*,task_id,revision,trace,supplements=(),candidate=False,alignment_ids=None,initial_retrieval_refs=None):
        body=self.prepare(snapshot,fact_ids,relation_ids,entity_ids,task_id=task_id,revision=revision,trace=trace,
                          supplements=supplements,candidate=candidate,alignment_ids=alignment_ids,initial_retrieval_refs=initial_retrieval_refs)
        from .knowledge import validate_evidence
        validate_evidence(body['evidence_refs'])
        encoded=canonical(body);signature=hmac.new(secret(),encoded.encode(),'sha256').hexdigest()
        write(DATA/'bundles'/(body['bundle_id'].split(':')[1]+'.json'),{'encoded':encoded,'signature':signature})
        return VerifiedBundle(encoded,signature)
    def get(self,bundle_id,*,task_id,revision,snapshot_id):
        if not re_id(bundle_id):raise ValidationError('BAD_BUNDLE_ID')
        raw=read(DATA/'bundles'/(bundle_id.split(':')[1]+'.json'));bundle=VerifiedBundle(**raw);b=bundle.data()
        if (b['task_id'],b['task_revision'],b['snapshot_id'])!=(task_id,revision,snapshot_id):raise ValidationError('STALE_TASK_OR_SNAPSHOT')
        from .knowledge import validate_evidence
        validate_evidence(b['evidence_refs'])
        return bundle

def re_id(value):
    return isinstance(value,str) and value.startswith('bundle:') and len(value)==71 and all(c in '0123456789abcdef' for c in value[7:])
