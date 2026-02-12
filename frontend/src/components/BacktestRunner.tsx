import { useState } from 'react';
import { Area, AreaChart, CartesianGrid, Line, LineChart, Tooltip, XAxis, YAxis } from 'recharts';
import { TradingAPI } from '../services/api';

export default function BacktestRunner() {
  const [form, setForm] = useState({ symbol: 'EURUSD', timeframe: 'H1', start: '', end: '' });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);

  const run = async () => {
    setRunning(true);
    try { setResult((await TradingAPI.runBacktest(form)).data); } finally { setRunning(false); }
  };

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold'>Backtest Runner</h2>
      <div className='grid grid-cols-4 gap-2 my-2'>
        <input className='p-2 rounded bg-slate-800' value={form.symbol} onChange={(e)=>setForm({...form,symbol:e.target.value})}/>
        <input className='p-2 rounded bg-slate-800' value={form.timeframe} onChange={(e)=>setForm({...form,timeframe:e.target.value})}/>
        <input className='p-2 rounded bg-slate-800' type='date' value={form.start} onChange={(e)=>setForm({...form,start:e.target.value})}/>
        <input className='p-2 rounded bg-slate-800' type='date' value={form.end} onChange={(e)=>setForm({...form,end:e.target.value})}/>
      </div>
      <button className='px-4 py-2 rounded bg-indigo-700' onClick={run} disabled={running}>{running ? 'Running...' : 'Run Backtest'}</button>
      {result && <div className='mt-3'><p>Return: {(result.total_return*100).toFixed(2)}% | Sharpe: {result.sharpe_ratio?.toFixed?.(2)}</p><div className='grid grid-cols-2'><LineChart width={420} height={200} data={result.equity_curve || []}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='time'/><YAxis/><Tooltip/><Line dataKey='value' stroke='#60a5fa'/></LineChart><AreaChart width={420} height={200} data={result.drawdown_curve || []}><CartesianGrid strokeDasharray='3 3'/><XAxis dataKey='time'/><YAxis/><Tooltip/><Area dataKey='value' stroke='#f97316' fill='#f97316'/></AreaChart></div></div>}
    </div>
  );
}
