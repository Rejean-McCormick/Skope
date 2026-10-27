"""Standalone Skope CLI for an existing read-only Wikidata SQLite index."""
import argparse
import json
import os
from pathlib import Path
from contextlib import closing
from .arketype import load_guidance
from .api import serve
from .db import connect,meta
from .scope import explore
from .export import bundle
from .project import default_database
from . import portfolio

TOOL=Path(__file__).resolve().parents[1]
ROOT=TOOL
DEFAULT_DB=default_database()

def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'portfolio':
        return portfolio_cli(argv[1:])
    p=argparse.ArgumentParser(description='Skope standalone — exploration locale de Wikidata')
    subs=p.add_subparsers(dest='action',required=True)
    for cmd in ('serve','meta','preview','export'):
        q=subs.add_parser(cmd)
        q.add_argument('--db',default=os.environ.get('SKOPE_DB',str(DEFAULT_DB)))
        if cmd in ('preview','export'):q.add_argument('--recipe',required=True)
        if cmd=='export':
            q.add_argument('--out',required=True)
            q.add_argument('--scope-key',default=None)
            q.add_argument('--guidance',default=None,help='Guide Arketype v1.4 non canonique facultatif')
        if cmd=='serve':
            q.add_argument('--kristal',default=None,help='Dossier du Kristal cible ; lecture seule')
            q.add_argument('--recipe',default=None)
            q.add_argument('--guidance',default=None)
            q.add_argument('--host',default='127.0.0.1')
            q.add_argument('--port',default=8767,type=int)
    args=p.parse_args(argv)
    if args.action=='serve':serve(args.db,args.host,args.port,args.recipe,args.guidance,args.kristal);return
    with closing(connect(args.db)) as db:
        if args.action=='meta': result=meta(db)
        else:
            recipe=json.loads(Path(args.recipe).read_text(encoding='utf-8-sig'))
            if args.action=='preview':result=explore(db,recipe)
            else:
                dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(bundle(db,recipe,args.scope_key,load_guidance(args.guidance)))
                result={'file':str(dest),'status':'working_non_canonical','raw_evidence_included':False}
    print(json.dumps(result,ensure_ascii=False,indent=2))

def portfolio_cli(argv):
    """First-class Kristal portfolio workflows, separate from individual scope campaigns."""
    ap = argparse.ArgumentParser(prog='skope portfolio',description='Portfolio enrichment: v11 -> Wikidata evidence proposals')
    sub = ap.add_subparsers(dest='command',required=True)
    q=sub.add_parser('inventory',help='Load a v11 ZIP or folders into Skope portfolio working state')
    q.add_argument('--input',required=True)
    q.add_argument('--work',required=True)
    q.add_argument('--include-metadata',action='store_true')
    q=sub.add_parser('prepare',help='Inventory + resumable discovery + unverified review CSV in one run')
    q.add_argument('--input',required=True)
    q.add_argument('--work',required=True)
    q.add_argument('--db',required=True)
    q.add_argument('--review-out',required=True)
    q.add_argument('--max-queries',type=int,default=25000)
    q.add_argument('--limit',type=int,default=8)
    q.add_argument('--suggest-draft',action='store_true')
    q=sub.add_parser('status',help='Show the portfolio status')
    q.add_argument('--work',required=True)
    q=sub.add_parser('discover',help='Search the existing Skope EncyK index in resumable batches')
    q.add_argument('--work',required=True)
    q.add_argument('--db',required=True)
    q.add_argument('--max-queries',type=int,default=1000)
    q.add_argument('--limit',type=int,default=8)
    q=sub.add_parser('suggest-draft',help='Choose unique exact-label candidates as UNVERIFIED draft seeds')
    q.add_argument('--work',required=True)
    q=sub.add_parser('review-csv',help='Export unverified matching candidates for human review')
    q.add_argument('--work',required=True)
    q.add_argument('--out',required=True)
    q=sub.add_parser('approve-review',help='Stage explicitly documented Q/P identity decisions')
    q.add_argument('--work',required=True)
    q.add_argument('--csv',required=True)
    q=sub.add_parser('export-seeds',help='Write QID inventory for source acquisition')
    q.add_argument('--work',required=True)
    q.add_argument('--out',required=True)
    q.add_argument('--include-draft',action='store_true')
    q=sub.add_parser('acquire',help='Resumable verified full Wikidata retrieval using Skope fast locator')
    q.add_argument('--work',required=True)
    q.add_argument('--db',required=True)
    q.add_argument('--profile',required=True)
    q.add_argument('--out',required=True)
    q.add_argument('--batch-size',type=int,default=200)
    q.add_argument('--max-batches',type=int,default=None)
    q.add_argument('--include-draft',action='store_true')
    q=sub.add_parser('propose',help='Prepare per-Kristal claims from full Wikidata records, no canon writes')
    q.add_argument('--work',required=True)
    q.add_argument('--evidence',required=True)
    q.add_argument('--out',required=True)
    q.add_argument('--max-claims',type=int,default=1000000)
    q.add_argument('--include-draft',action='store_true')
    args=ap.parse_args(argv)
    if args.command=='inventory':
        data=portfolio.inventory(args.input,args.work,args.include_metadata)
    elif args.command=='prepare':
        portfolio.inventory(args.input,args.work)
        data=portfolio.discover(args.work,args.db,args.max_queries,args.limit)
        if args.suggest_draft:
            data['draft']=portfolio.suggest_drafts(args.work)
        data['review']=portfolio.export_review(args.work,args.review_out)
    elif args.command=='status':data=portfolio.status(args.work)
    elif args.command=='discover':data=portfolio.discover(args.work,args.db,args.max_queries,args.limit)
    elif args.command=='suggest-draft':data=portfolio.suggest_drafts(args.work)
    elif args.command=='review-csv':data=portfolio.export_review(args.work,args.out)
    elif args.command=='approve-review':data=portfolio.approve_review(args.work,args.csv)
    elif args.command=='export-seeds':data=portfolio.export_seeds(args.work,args.out,args.include_draft)
    elif args.command=='acquire':data=portfolio.acquire(args.work,args.db,args.profile,args.out,args.batch_size,args.max_batches,args.include_draft)
    else:data=portfolio.propose(args.work,args.evidence,args.out,args.max_claims,args.include_draft)
    print(json.dumps(data,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
