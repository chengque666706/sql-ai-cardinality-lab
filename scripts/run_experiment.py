"""Collect real PostgreSQL plans. Requires Docker and the generated SF=1 files."""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, random, statistics, subprocess, time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = 'sql-ai-cardinality-lab-pg'
DB = 'cardinality_lab'
SETTINGS = """SET search_path=tpch,synthetic,public;
SET max_parallel_workers_per_gather=0; SET jit=off;
SET work_mem='64MB'; SET default_statistics_target=100;
SET statement_timeout='180s'; SET timezone='Asia/Shanghai';"""

def sql(text):
    p = subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-q','-A','-t',
                        '-v','ON_ERROR_STOP=1','-U','postgres','-d',DB],
                       input=text, text=True, encoding='utf-8', capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr)
    return p.stdout.strip()

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def csv_write(path, rows):
    if not rows: return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def initialize():
    # Refuse to overwrite a database already containing these experiment schemas.
    if sql("SELECT count(*) FROM pg_namespace WHERE nspname IN ('tpch','synthetic')") != '0':
        raise RuntimeError('Experiment schemas already exist. Use --collect to preserve data.')
    data=ROOT/'data/tpch_sf1'
    schema=(data/'schema.sql').read_text(encoding='utf-8')
    sql('CREATE SCHEMA tpch; SET search_path=tpch;'+schema)
    for table in ['region','nation','supplier','customer','part','partsupp','orders','lineitem']:
        started=time.perf_counter()
        sql(f"COPY tpch.{table} FROM '/tpch-data/{table}.csv' WITH (FORMAT csv, DELIMITER '|', NULL '\\N', QUOTE '\"', ESCAPE '\"');")
        print(f'Imported {table}: {time.perf_counter()-started:.2f}s',flush=True)
    sql((ROOT/'sql/01_constraints.sql').read_text(encoding='utf-8'))
    sql((ROOT/'sql/02_synthetic.sql').read_text(encoding='utf-8'))
    sql('VACUUM (ANALYZE);')

def snapshot_stats(path):
    data=json.loads(sql("SELECT coalesce(json_agg(t),'[]') FROM (SELECT schemaname,tablename,attname,null_frac,avg_width,n_distinct,most_common_vals::text,most_common_freqs::text,histogram_bounds::text,correlation FROM pg_stats WHERE schemaname IN ('tpch','synthetic') ORDER BY schemaname,tablename,attname)t"))
    save_json(path,data)

def collect():
    workload=json.loads((ROOT/'scripts/workload.json').read_text(encoding='utf-8'))
    out=ROOT/'results'
    if (out/'query_runs.csv').exists():
        raise RuntimeError('Existing results present; archive results directory before another run.')
    out.mkdir(exist_ok=True)
    versions={'timestamp_shanghai':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
              'postgresql':sql('SELECT version()'), 'host_platform':platform.platform(),
              'python':platform.python_version(),'warmups':1,'measured_repeats':3,
              'random_seed':20261002,'session_settings_sql':SETTINGS,
              'data_scale_factor':1,'query_count':len(workload),
              'docker_image':json.loads(subprocess.check_output(['docker','image','inspect','postgres:17.6'],text=True))[0]['RepoDigests'],
              'settings':json.loads(sql(SETTINGS+"SELECT json_object_agg(name,setting) FROM pg_settings WHERE name IN ('shared_buffers','work_mem','effective_cache_size','random_page_cost','seq_page_cost','cpu_tuple_cost','default_statistics_target','max_parallel_workers_per_gather','jit','autovacuum','server_version','block_size')"))}
    save_json(out/'environment.json',versions)
    counts=json.loads(sql("SELECT json_agg(t) FROM (SELECT schemaname,relname,n_live_tup FROM pg_stat_user_tables ORDER BY schemaname,relname)t"))
    save_json(out/'table_estimates.json',counts)
    exact=[]
    for row in counts:
        exact.append({'schema':row['schemaname'],'table':row['relname'],'rows':int(sql(f"SELECT count(*) FROM {row['schemaname']}.{row['relname']}"))})
    csv_write(out/'table_counts.csv',exact)
    queries=[]; nodes=[]
    # Plain ANALYZE control separates statistics refresh from extended statistics.
    for phase in ['baseline','reanalyze_control','extended']:
        if phase=='baseline':
            sql("DO $$ DECLARE r record; BEGIN FOR r IN SELECT schemaname,statistics_name FROM pg_statistic_ext JOIN pg_stats_ext ON stxname=statistics_name WHERE schemaname='synthetic' LOOP EXECUTE format('DROP STATISTICS IF EXISTS %I.%I',r.schemaname,r.statistics_name); END LOOP; END $$;")
        elif phase=='reanalyze_control':
            for t in exact:
                if t['schema']=='synthetic':sql(f"ANALYZE synthetic.{t['table']};")
        else:
            sql((ROOT/'sql/03_extended_stats.sql').read_text(encoding='utf-8'))
        snapshot_stats(out/f'stats_{phase}.json')
        active=workload if phase=='baseline' else [q for q in workload if q['source']=='synthetic']
        for repeat in range(4):
            order=list(active); random.Random(20261002+repeat).shuffle(order)
            for q in order:
                query=q['sql'].rstrip(';')
                raw=sql(SETTINGS+'\nEXPLAIN (ANALYZE, BUFFERS, SETTINGS, VERBOSE, FORMAT JSON) '+query+';')
                plan=json.loads(raw)
                name=f"{phase}/{q['id']}_r{repeat}.json"
                save_json(out/'plans'/name,plan)
                root=plan[0]['Plan']; est=root['Plan Rows']; act=root['Actual Rows']
                row={'phase':phase,'query_id':q['id'],'title':q['title'],'group':q['group'],'source':q['source'],
                     'repeat':repeat,'is_warmup':repeat==0,'plan_rows':est,'actual_rows':act,
                     'actual_loops':root['Actual Loops'],'q_error':max(est/act,act/est) if act>0 and est>0 else '',
                     'q_error_safe':max(max(est,1)/max(act,1),max(act,1)/max(est,1)),
                     'zero_actual':act==0,'total_cost':root['Total Cost'],
                     'actual_total_time_ms':root['Actual Total Time'],
                     'execution_time_ms':plan[0]['Execution Time'],'planning_time_ms':plan[0]['Planning Time'],
                     'root_node_type':root['Node Type'],'sql_sha256':hashlib.sha256(query.encode()).hexdigest(),
                     'plan_file':'plans/'+name}
                queries.append(row)
                def walk(node,path='0',parent=''):
                    e=node['Plan Rows'];a=node.get('Actual Rows',0);loops=node.get('Actual Loops',0)
                    nodes.append({'phase':phase,'query_id':q['id'],'repeat':repeat,'is_warmup':repeat==0,
                        'node_path':path,'parent_path':parent,'node_type':node['Node Type'],
                        'relation':node.get('Relation Name',''),'alias':node.get('Alias',''),
                        'plan_rows_per_loop':e,'actual_rows_per_loop':a,'actual_loops':loops,
                        'actual_rows_total_approx':a*loops,'q_error':max(e/a,a/e) if e>0 and a>0 and loops>0 else '',
                        'q_error_safe':max(max(e,1)/max(a,1),max(a,1)/max(e,1)) if loops>0 else '',
                        'executed':loops>0,'zero_actual':a==0,'total_cost':node['Total Cost'],
                        'actual_total_time_ms_per_loop':node.get('Actual Total Time',''),
                        'filter':node.get('Filter',''),'join_filter':node.get('Join Filter',''),
                        'hash_cond':node.get('Hash Cond',''),'index_cond':node.get('Index Cond',''),
                        'plan_file':'plans/'+name})
                    for i,c in enumerate(node.get('Plans',[])):walk(c,f'{path}.{i}',path)
                walk(root)
                print(f"{phase} {q['id']} r{repeat} E={est} A={act} time={row['execution_time_ms']}ms",flush=True)
                csv_write(out/'query_runs.csv',queries);csv_write(out/'node_runs.csv',nodes)
    ext=json.loads(sql("SELECT coalesce(json_agg(t),'[]') FROM (SELECT schemaname,tablename,statistics_name,attnames,kinds,n_distinct,dependencies FROM pg_stats_ext ORDER BY schemaname,tablename,statistics_name)t"))
    save_json(out/'extended_statistics.json',ext)
    print(f'Completed: {len(queries)} plan executions, {len(nodes)} node records',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--init',action='store_true');parser.add_argument('--collect',action='store_true');args=parser.parse_args()
    if not args.init and not args.collect:parser.error('Use --init and/or --collect')
    if args.init:initialize()
    if args.collect:collect()
