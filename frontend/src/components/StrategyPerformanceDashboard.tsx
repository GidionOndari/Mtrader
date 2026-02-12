import { useEffect, useState } from 'react';
import { Area, AreaChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import { TradingAPI } from '../services/api';

export default function StrategyPerformanceDashboard() {
  const [data, setData] = useState<any>({ metrics: {}, equity: [], drawdown: [], monthly: [] });
  useEffect(()=>{ TradingAPI.getStrategyPerformance().then((r)=>setData(r.data || {metrics:{}, equity:[], drawdown:[], monthly:[]})); },[]);

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold'>Strategy Performance</h2>
      <div className='grid grid-cols-3 gap-3 text-sm my-2'>
        <div>Win Rate: {Math.round((data.metrics.win_rate||0)*100)}%</div>
        <div>Sharpe: {data.metrics.sharpe?.toFixed?.(2) ?? data.metrics.sharpe}</div>
        <div>Max DD: {Math.round((data.metrics.max_drawdown||0)*100)}%</div>
      </div>
      <div className='grid grid-cols-2 gap-4'>
        <LineChart width={420} height={200} data={data.equity}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='time'/><YAxis/><Tooltip/><Line dataKey='value' stroke='#22c55e'/></LineChart>
        <AreaChart width={420} height={200} data={data.drawdown}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='time'/><YAxis/><Tooltip/><Area dataKey='value' stroke='#ef4444' fill='#ef4444'/></AreaChart>
      </div>
      <div className='mt-3 grid grid-cols-6 gap-1'>{(data.monthly||[]).map((m:any)=><div key={m.month} className='rounded p-2 text-xs' style={{background: m.value>=0?'#14532d':'#7f1d1d'}}>{m.month}<br/>{(m.value*100).toFixed(1)}%</div>)}</div>
    </div>
  );
}
