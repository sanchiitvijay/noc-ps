import { useEffect, useState } from 'react';
import { getActivityLog, ingestFile } from '../services/api';
import { useStore } from '../store';

export default function Admin() {
  const say = useStore((state) => state.say);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [activity, setActivity] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState('');

  const loadActivity = (nextPage = page) =>
    getActivityLog({ page: nextPage, page_size: 25 })
      .then((result) => {
        setActivity(Array.isArray(result) ? result : result?.data || result?.items || []);
        setTotal(result?.total || 0);
        setPage(result?.page || nextPage);
      })
      .catch((requestError) => setError(requestError.message));

  useEffect(() => {
    loadActivity(1);
  }, []);

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;

    const form = event.currentTarget;
    setBusy(true);
    setError('');
    setMessage('');

    try {
      const result = await ingestFile(file);
      const acceptedMessage = result?.message || 'File accepted for ingestion.';
      const jobId = result?.job_id ? ` Job ID: ${result.job_id}` : '';
      setMessage(`${acceptedMessage}${jobId}`);
      say('File accepted for ingestion');
      setFile(null);
      form.reset();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <section className="c">
        <h3>Ingest events or tickets</h3>
        <form
          onSubmit={upload}
          style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <input
            type="file"
            accept=".csv,.xlsx"
            required
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <button className="p" disabled={!file || busy}>
            {busy ? 'Uploading...' : 'Upload file'}
          </button>
        </form>
        <p className="mu">Accepted formats: CSV and XLSX.</p>
        {message && <div role="status">{message}</div>}
        {error && <div role="alert" style={{ color: '#DC2626' }}>{error}</div>}
      </section>

      <section className="c">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h3>Activity log</h3>
          <button onClick={() => loadActivity(1)}>Refresh</button>
        </div>
        {error && <div role="alert" style={{ color: '#DC2626' }}>{error}</div>}
        {activity.length ? activity.map((item, index) => (
          <div className="row" key={item.id || `${item.timestamp}-${index}`}>
            <span style={{ flex: 1 }}>
              {item.username || item.user_id || 'User'}  |  {item.endpoint_path || item.action || 'Action'}
            </span>
            <span className="mu">{item.created_at || item.timestamp || ''}</span>
          </div>
        )) : <span className="mu">No activity records returned.</span>}
        <div className="row" style={{ justifyContent: 'flex-end' }}>
          <button disabled={page <= 1} onClick={() => loadActivity(page - 1)}>
            Previous
          </button>
          <span className="mu">Page {page}  |  {total.toLocaleString()} records</span>
          <button disabled={page * 25 >= total} onClick={() => loadActivity(page + 1)}>
            Next
          </button>
        </div>
      </section>
    </>
  );
}
