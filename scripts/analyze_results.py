"""Derive query-level summaries and publication charts from saved measured plans."""
import csv, json, math, statistics, sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.python_deps'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

def read(name):
    with (ROOT/'results'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
    with (ROOT/'results'/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    runs=read('query_runs.csv');groups=defaultdict(list)
    for r in runs:
        if r['is_warmup']=='False':groups[r['phase'],r['query_id']].append(r)
    summaries=[]
    for (phase,qid),items in groups.items():
        if len(items)!=3:raise ValueError(f'Expected three measurements for {phase}/{qid}')
        if len({(r['plan_rows'],r['actual_rows']) for r in items})!=1:raise ValueError('Cardinality changed across repeats')
        r=items[0]
        row={k:r[k] for k in ['phase','query_id','title','group','source','plan_rows','actual_rows','q_error','q_error_safe','zero_actual','total_cost','root_node_type']}
        for key in ['execution_time_ms','planning_time_ms','actual_total_time_ms']:
            nums=[float(x[key]) for x in items]
            row[key+'_median']=statistics.median(nums)
            row[key+'_min']=min(nums);row[key+'_max']=max(nums)
        row['measured_repeats']=len(items);row['representative_plan']=r['plan_file'];summaries.append(row)
    summaries.sort(key=lambda x:({'baseline':0,'reanalyze_control':1,'extended':2}[x['phase']],x['query_id']))
    write('query_summary.csv',summaries)
    grouped=defaultdict(list)
    for r in summaries:grouped[r['phase'],r['group']].append(r)
    stats=[]
    for (phase,group),items in grouped.items():
        q=[float(r['q_error']) for r in items if r['q_error']!='']
        stats.append({'phase':phase,'group':group,'n_queries':len(items),'n_positive':len(q),'n_zero':sum(r['zero_actual']=='True' for r in items),
                      **{f'q_error_p{p}':float(np.percentile(q,p,method='linear')) if q else '' for p in [50,90,99]},'q_error_max':max(q) if q else ''})
    write('qerror_statistics.csv',stats)
    f=ROOT/'figures';f.mkdir(exist_ok=True)
    for font in ['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf']:
        if Path(font).exists():
            font_manager.fontManager.addfont(font);plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name();break
    plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'figure.dpi':120,'savefig.dpi':220})
    blue='#2563a6';orange='#d45a35';green='#1d826c'
    def save(name):
        plt.tight_layout();plt.savefig(f/(name+'.png'),bbox_inches='tight');plt.savefig(f/(name+'.svg'),bbox_inches='tight');plt.close()
        svg=f/(name+'.svg')
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    base=[r for r in summaries if r['phase']=='baseline'];positive=[r for r in base if float(r['actual_rows'])>0]
    fig,ax=plt.subplots(figsize=(9,6))
    for source,label,col in [('tpch','TPC-H 派生查询',blue),('synthetic','合成对照查询',orange)]:
        sub=[r for r in positive if r['source']==source];ax.scatter([float(r['actual_rows']) for r in sub],[float(r['plan_rows']) for r in sub],label=label,color=col,s=48)
        labels=defaultdict(list)
        for r in sub:
            if float(r['q_error'])>=5:labels[float(r['actual_rows']),float(r['plan_rows'])].append(r['query_id'])
        for point,ids in labels.items():ax.annotate(' / '.join(ids),point,xytext=(5,4),textcoords='offset points',fontsize=9)
    ax.plot([1,1e6],[1,1e6],color='#777777',linestyle='--',label='估计 = 实际');ax.set(xscale='log',yscale='log',xlabel='Actual Rows（实际输出行数）',ylabel='Plan Rows（估计输出行数）',title='基线查询的估计基数与实际基数');ax.legend();ax.grid(alpha=.15);save('B01_estimated_vs_actual')
    tp=[r for r in base if r['source']=='tpch'];x=np.arange(len(tp));fig,ax=plt.subplots(figsize=(11,4.8))
    ax.bar(x-.19,[float(r['plan_rows']) for r in tp],.38,label='估计行数',color=blue);ax.bar(x+.19,[float(r['actual_rows']) for r in tp],.38,label='实际行数',color=orange)
    ax.set(yscale='log',xticks=x,xticklabels=[r['query_id'] for r in tp],ylabel='输出行数（对数坐标）',title='TPC-H 单表与连接查询的基数比较');ax.legend();ax.grid(axis='y',alpha=.15);save('B02_tpch_cardinalities')
    fig,ax=plt.subplots(figsize=(11,5));x=np.arange(len(positive))
    colors=[blue if r['source']=='tpch' else orange for r in positive]
    ax.bar(x,[float(r['q_error']) for r in positive],color=colors)
    ax.axhline(1,color='#666666',linestyle='--');ax.set(yscale='log',ylim=(.8,400),xticks=x,xticklabels=[r['query_id'] for r in positive],ylabel='Q-error（越接近 1 越好）',title='不同查询的基线 Q-error')
    for i,r in enumerate(positive):
        if float(r['q_error'])>=5:ax.text(i,float(r['q_error'])*1.10,f"{float(r['q_error']):.1f}",ha='center',fontsize=9)
    ax.text(.01,.98,'蓝色：TPC-H；橙色：合成数据；零行负控 S17 单独分析',transform=ax.transAxes,va='top',fontsize=10);ax.grid(axis='y',alpha=.15);save('C01_query_qerror')
    lookup={(r['phase'],r['query_id']):r for r in summaries}
    ids=['S15','S16'];fig,ax=plt.subplots(figsize=(8,4.8));x=np.arange(2)
    ax.bar(x-.2,[float(lookup['baseline',q]['plan_rows']) for q in ids],.4,label='估计行数',color=blue);ax.bar(x+.2,[float(lookup['baseline',q]['actual_rows']) for q in ids],.4,label='实际行数',color=orange)
    ax.set(yscale='log',ylim=(10,9000),xticks=x,xticklabels=['S15 独立属性\n相同边际频率','S16 强相关属性\n相同边际频率'],ylabel='输出行数（对数坐标）',title='保持边际分布相同 只改变属性相关性')
    for i,q in enumerate(ids):
        r=lookup['baseline',q];ax.text(i,max(float(r['plan_rows']),float(r['actual_rows']))*1.3,f"Q-error = {float(r['q_error']):g}",ha='center')
    ax.legend();save('C02_correlation_control')
    ids=['S15','S16','S18','S19','S20'];x=np.arange(len(ids));fig,ax=plt.subplots(figsize=(10,5))
    for offset,phase,label,col in [(-.25,'baseline','基线',orange),(0,'reanalyze_control','仅重新 ANALYZE',blue),(.25,'extended','扩展统计',green)]:
        values=[float(lookup[phase,q]['q_error']) for q in ids];ax.bar(x+offset,values,.25,label=label,color=col)
    ax.set(yscale='log',ylim=(.8,400),xticks=x,xticklabels=['S15\n独立','S16\n相关','S18\n倾斜热门','S19\n倾斜稀有','S20\n跨表相关'],ylabel='Q-error（越接近 1 越好）',title='扩展统计对同表相关性及跨表相关性的影响');ax.legend();ax.grid(axis='y',alpha=.15);save('C03_extended_statistics')
    workload=json.loads((ROOT/'scripts/workload.json').read_text(encoding='utf-8'))
    report=ROOT/'reports';report.mkdir(exist_ok=True)
    text='# SQL 查询清单\n\n共 20 条教学 SPJ 查询，12 条在 TPC-H 数据上派生，8 条在合成数据上执行；不是官方 TPC-H Q1 至 Q22，也不产生 TPC-H 性能评分。\n'
    for q in workload:text+=f"\n## {q['id']} {q['title']}\n\n场景：`{q['group']}`；数据：`{q['source']}`。\n\n```sql\n{q['sql']}\n```\n"
    (report/'SQL查询清单.md').write_text(text,encoding='utf-8')
    print(f'Wrote {len(summaries)} query/phase summaries and 5 figures.')

if __name__=='__main__':main()
