import { useEffect, useState } from 'react';
import { TradingAPI } from '../services/api';
import { useRealTimeData } from '../hooks/useRealTimeData';

export default function ActivePositionsTable() {
  const [rows, setRows] = useState<any[]>([]);
  const live = useRealTimeData<any[]>('position_updates', 'position_updates', []);

  useEffect(()=>{ TradingAPI.getPositions().then((r)=>setRows(r.data || [])); },[]);
  useEffect(()=>{ if (live?.length) setRows(live); },[live]);

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold'>Active Positions</h2>
      <table className='w-full text-sm'>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Current</th><th>P&L</th><th>Action</th></tr></thead>
        <tbody>{rows.map((p)=> <tr key={p.id}><td>{p.symbol}</td><td>{p.quantity}</td><td>{p.entry_price}</td><td>{p.current_price}</td><td>{p.pnl} ({p.pnl_pct}%)</td><td><button className='text-rose-300' onClick={()=>TradingAPI.closePosition(p.id)}>Close</button></td></tr>)}</tbody>
      </table>
    </div>
  );
}
