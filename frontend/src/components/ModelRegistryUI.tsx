import { useEffect, useState } from 'react';
import { TradingAPI } from '../services/api';

export default function ModelRegistryUI() {
  const [models, setModels] = useState<any[]>([]);
  const [filter, setFilter] = useState('');
  const load = async () => setModels((await TradingAPI.getModels()).data || []);
  useEffect(()=>{ load(); },[]);
  const rows = models.filter((m)=> !filter || m.stage===filter || m.status===filter);

  return (
    <div className='rounded-xl p-4 bg-slate-900 text-slate-100'>
      <h2 className='text-lg font-semibold'>Model Registry</h2>
      <select className='p-2 rounded bg-slate-800 my-2' value={filter} onChange={(e)=>setFilter(e.target.value)}>
        <option value=''>All</option><option value='development'>Development</option><option value='staging'>Staging</option><option value='production'>Production</option>
      </select>
      <table className='w-full text-sm'>
        <thead><tr><th>Name</th><th>Version</th><th>Status</th><th>Metrics</th><th>Actions</th></tr></thead>
        <tbody>{rows.map((m)=> <tr key={m.id}><td>{m.name}</td><td>{m.version}</td><td>{m.stage}</td><td>Sharpe {m.metrics?.sharpe}</td><td className='space-x-2'><button onClick={()=>TradingAPI.promoteModel(m.id,'staging')} className='text-amber-300'>Staging</button><button onClick={()=>TradingAPI.promoteModel(m.id,'production')} className='text-emerald-300'>Prod</button><button onClick={()=>TradingAPI.rollbackModel(m.name)} className='text-rose-300'>Rollback</button></td></tr>)}</tbody>
      </table>
    </div>
  );
}
