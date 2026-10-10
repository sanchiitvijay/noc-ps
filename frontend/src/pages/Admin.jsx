import { useEffect, useRef, useState } from "react";
import {
  FaUserPlus, FaTimes, FaUpload, FaSync,
  FaHistory, FaFileCsv, FaCheckCircle, FaTimesCircle, FaSpinner, FaDatabase,
  FaFileAlt, FaClock,
} from "react-icons/fa";
import Pagination from "../components/Pagination";
import { createUser, getActivityLog, getIngestJob, getIngestJobs, ingestDataFile } from "../services/api";
import { useStore } from "../store";

const TERMINAL = new Set(["succeeded", "failed", "interrupted"]);

const STATUS_STYLE = {
  succeeded: { icon: FaCheckCircle, className: "text-good", bg: "bg-good-bg" },
  failed: { icon: FaTimesCircle, className: "text-p1", bg: "bg-p1-bg" },
  interrupted: { icon: FaTimesCircle, className: "text-p1", bg: "bg-p1-bg" },
  running: { icon: FaFileAlt, className: "text-brand", bg: "bg-brand-tint dark:bg-brand/20" },
  queued: { icon: FaClock, className: "text-ink-3", bg: "bg-paper-3 dark:bg-white/10" },
};

function JobRow({ job }) {
  const style = STATUS_STYLE[job.status] || STATUS_STYLE.queued;
  const Icon = style.icon;
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-paper-2 px-3.5 py-3 dark:border-white/10 dark:bg-white/5">
      <span className={`grid h-10 w-10 flex-none place-items-center rounded-lg ${style.bg} ${style.className}`}>
        <Icon />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <b className="truncate text-[13px] text-ink dark:text-white">{job.filename}</b>
          <span className="rounded-full bg-paper-3 px-2 py-0.5 text-[11px] font-semibold text-ink-2 dark:bg-white/10">
            {job.dataset || job.status}
          </span>
        </div>
        <span className="text-[12px] text-ink-3">
          Job {job.id}
          {job.rows_processed ? ` · ${job.rows_processed} rows` : ""}
          {job.stage ? ` · ${job.stage}` : ""}
          {job.error_message ? ` · ${job.error_message}` : ""}
        </span>
        {typeof job.progress === "number" && job.progress > 0 && job.progress < 100 && (
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper-3 dark:bg-white/10">
            <i className="block h-full rounded-full bg-brand transition-[width] duration-300" style={{ width: `${job.progress}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}

function JobSkeleton() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-line bg-paper-2 px-3.5 py-3 dark:border-white/10 dark:bg-white/5" aria-hidden="true">
      <span className="grid h-10 w-10 flex-none place-items-center rounded-lg bg-brand-tint text-brand/50 dark:bg-brand/10">
        <FaDatabase />
      </span>
      <div className="min-w-0 flex-1">
        <div className="skeleton h-3.5 w-1/2 rounded" />
        <div className="skeleton mt-1.5 h-3 w-1/3 rounded" />
      </div>
    </div>
  );
}

export default function Admin() {
  const say = useStore((state) => state.say);
  const [file, setFile] = useState(null);
  const [ingestKind, setIngestKind] = useState("excel");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [job, setJob] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const pollRef = useRef(null);

  const [activity, setActivity] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [activityError, setActivityError] = useState("");
  const [activityLoading, setActivityLoading] = useState(false);

  const [showSignupModal, setShowSignupModal] = useState(false);
  const [signupForm, setSignupForm] = useState({ username: "", email: "", password: "", role: "ANALYST" });
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupMsg, setSignupMsg] = useState("");

  const loadActivity = (nextPage = page) => {
    setActivityLoading(true);
    getActivityLog({ page: nextPage, page_size: 15 })
      .then((result) => {
        setActivity(result.data || []);
        setTotal(result.total || 0);
        setPage(result.page || nextPage);
        setActivityError("");
      })
      .catch((requestError) => setActivityError(requestError.message))
      .finally(() => setActivityLoading(false));
  };

  const loadJobs = () => {
    setJobsLoading(true);
    getIngestJobs({ page: 1, page_size: 8 })
      .then((result) => setJobs(result.data || []))
      .catch(() => {})
      .finally(() => setJobsLoading(false));
  };

  useEffect(() => {
    loadActivity(1);
    loadJobs();
    return () => window.clearInterval(pollRef.current);
  }, []);

  const pollJob = (jobId) => {
    window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const current = await getIngestJob(jobId);
        setJob(current);
        if (TERMINAL.has(current.status)) {
          window.clearInterval(pollRef.current);
          setMessage(
            `${current.filename} — ${current.status}${current.rows_processed ? ` · ${current.rows_processed} rows` : ""}`,
          );
          if (current.status === "succeeded") say(`Ingestion job ${jobId} completed`);
          loadJobs();
        }
      } catch {
        window.clearInterval(pollRef.current);
      }
    }, 1500);
  };

  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;
    const form = event.currentTarget;
    setBusy(true);
    setError("");
    setMessage("");
    setJob(null);

    try {
      const result = await ingestDataFile(file, ingestKind);
      setJob(result);
      setMessage(result?.message || "File accepted for ingestion.");
      say("File accepted for ingestion");
      setFile(null);
      form.reset();
      loadJobs();
      if (result?.job_id) pollJob(result.job_id);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setSignupBusy(true);
    setSignupMsg("");
    try {
      await createUser(signupForm);
      say(`User ${signupForm.username} created successfully!`);
      setShowSignupModal(false);
      setSignupForm({ username: "", email: "", password: "", role: "ANALYST" });
    } catch (err) {
      setSignupMsg(err.message);
    } finally {
      setSignupBusy(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-6xl gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-[22px] font-bold tracking-tight text-ink dark:text-white">Administration Configuration</h2>
        <button
          onClick={() => setShowSignupModal(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-[13.5px] font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi"
        >
          <FaUserPlus /> Add New User
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <div className="overflow-hidden rounded-card border border-line bg-paper shadow-card dark:border-white/10 dark:bg-[#0c2435]">
            <div className="border-b border-line bg-paper-2 px-5 py-4 dark:border-white/10 dark:bg-white/5">
              <h3 className="flex items-center gap-2 font-semibold text-ink dark:text-white">
                <FaFileCsv className="text-good" /> Data Ingestion
              </h3>
            </div>
            <div className="p-5">
              <form onSubmit={upload} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-[13px] font-semibold text-ink-2">Dataset</label>
                  <select
                    value={ingestKind}
                    onChange={(event) => setIngestKind(event.target.value)}
                    className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none focus:border-brand dark:border-white/15 dark:bg-white/5 dark:text-white"
                  >
                    <option value="excel">Auto-detect (CSV / Excel)</option>
                    <option value="error">Event log CSV</option>
                    <option value="ticket">Ticket CSV</option>
                  </select>
                </div>

                <div className="rounded-lg border-2 border-dashed border-line-strong p-4 text-center dark:border-white/15">
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    required
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                    className="block w-full cursor-pointer text-[13px] text-ink-3 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-tint file:px-3 file:py-2 file:text-[13px] file:font-semibold file:text-brand hover:file:bg-brand-tint-2"
                  />
                  <p className="mt-2 text-[12px] text-ink-3">Accepted formats: CSV and XLSX</p>
                </div>

                <button
                  disabled={!file || busy}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand py-2.5 text-[13.5px] font-semibold text-white shadow-sm transition-colors hover:bg-brand-hi disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? <FaSpinner className="animate-spin" /> : <FaUpload />}
                  {busy ? "Uploading…" : "Upload File"}
                </button>
              </form>

              {message && (
                <div className="mt-4 rounded-lg border border-good/25 bg-good-bg px-3 py-2.5 text-[13px] text-good">{message}</div>
              )}
              {error && (
                <div role="alert" className="mt-4 rounded-lg border border-p1/25 bg-p1-bg px-3 py-2.5 text-[13px] text-p1-ink">{error}</div>
              )}
              {job && !TERMINAL.has(job.status) && (
                <div className="mt-4">
                  <JobRow job={job} />
                </div>
              )}
            </div>
          </div>

          <div className="overflow-hidden rounded-card border border-line bg-paper shadow-card dark:border-white/10 dark:bg-[#0c2435]">
            <div className="flex items-center justify-between border-b border-line bg-paper-2 px-5 py-4 dark:border-white/10 dark:bg-white/5">
              <h3 className="flex items-center gap-2 font-semibold text-ink dark:text-white">
                <FaDatabase className="text-ink-3" /> Recent ingest jobs
              </h3>
              <button onClick={loadJobs} className="text-[13px] font-medium text-ink-3 transition-colors hover:text-brand">
                Refresh
              </button>
            </div>
            <div className="grid gap-2 p-4">
              {jobsLoading
                ? Array.from({ length: 3 }, (_, index) => <JobSkeleton key={index} />)
                : jobs.length
                  ? jobs.map((item) => <JobRow key={item.id} job={item} />)
                  : (
                    <p className="py-4 text-center text-[13px] text-ink-3">No ingest jobs recorded.</p>
                  )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          <div className="flex h-full flex-col overflow-hidden rounded-card border border-line bg-paper shadow-card dark:border-white/10 dark:bg-[#0c2435]">
            <div className="flex items-center justify-between border-b border-line bg-paper-2 px-5 py-4 dark:border-white/10 dark:bg-white/5">
              <h3 className="flex items-center gap-2 font-semibold text-ink dark:text-white">
                <FaHistory className="text-ink-3" /> System Activity Log
              </h3>
              <button
                onClick={() => loadActivity(1)}
                className="flex items-center gap-1.5 text-[13px] text-ink-3 transition-colors hover:text-brand"
              >
                <FaSync className={activityLoading ? "animate-spin" : ""} /> Refresh
              </button>
            </div>

            <div className="flex-1 overflow-x-auto">
              {activityError && <div className="m-4 rounded-lg border border-p1/25 bg-p1-bg p-3 text-[13px] text-p1-ink">{activityError}</div>}

              <table className="min-w-full border-collapse text-[13px]">
                <thead className="bg-paper-2 dark:bg-white/5">
                  <tr>
                    {["User", "Action", "Endpoint", "Status", "Time"].map((h) => (
                      <th key={h} className="border-b border-line px-5 py-2.5 text-left text-[11px] font-semibold tracking-wider text-ink-3 uppercase dark:border-white/10">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line dark:divide-white/10">
                  {activity.length > 0 ? activity.map((item, index) => (
                    <tr key={item.id || `${item.created_at}-${index}`} className="transition-colors hover:bg-paper-2 dark:hover:bg-white/5">
                      <td className="px-5 py-2.5 font-medium whitespace-nowrap text-ink dark:text-white">
                        {item.username || item.user_id || "System"}
                      </td>
                      <td className="px-5 py-2.5 whitespace-nowrap text-ink-2">{item.action || "—"}</td>
                      <td className="px-5 py-2.5 font-mono text-[12px] whitespace-nowrap text-ink-3">
                        {item.endpoint || item.endpoint_path || "—"}
                      </td>
                      <td className="px-5 py-2.5 whitespace-nowrap">
                        <span className={`rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${
                          Number(item.response_status) >= 400
                            ? "bg-p1-bg text-p1-ink"
                            : "bg-good-bg text-good"
                        }`}>
                          {item.response_status ?? "—"}
                        </span>
                      </td>
                      <td className="px-5 py-2.5 text-right whitespace-nowrap text-ink-3">
                        {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={5} className="px-5 py-12 text-center text-[13px] text-ink-3">
                        {activityLoading ? "Loading activity…" : "No activity records found."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between border-t border-line bg-paper-2 px-5 py-3 dark:border-white/10 dark:bg-white/5">
              <span className="text-[13px] text-ink-2">
                {total.toLocaleString()} total records
              </span>
              <Pagination
                page={page}
                totalPages={Math.max(1, Math.ceil(total / 15))}
                disabled={activityLoading}
                onPageChange={(next) => loadActivity(next)}
                windowSize={5}
                className="flex flex-wrap items-center justify-center gap-1.5"
              />
            </div>
          </div>
        </div>
      </div>

      {showSignupModal && (
        <div className="fixed inset-0 z-50 grid place-items-center p-4">
          <div className="absolute inset-0 bg-[rgba(2,20,33,0.55)] backdrop-blur-sm" onClick={() => setShowSignupModal(false)} />
          <div className="animate-rise relative w-full max-w-md overflow-hidden rounded-2xl border border-line bg-paper shadow-pop dark:border-white/10 dark:bg-[#0c2435]">
            <div className="flex items-center justify-between border-b border-line px-6 py-4 dark:border-white/10">
              <h3 className="flex items-center gap-2 text-[16px] font-bold text-ink dark:text-white">
                <FaUserPlus className="text-brand" /> Create System User
              </h3>
              <button onClick={() => setShowSignupModal(false)} className="text-ink-3 transition-colors hover:text-ink" aria-label="Close">
                <FaTimes />
              </button>
            </div>
            <form onSubmit={handleSignup}>
              <div className="space-y-4 px-6 py-5">
                {signupMsg && (
                  <div className="rounded-lg border border-p1/25 bg-p1-bg px-3 py-2 text-[13px] text-p1-ink">{signupMsg}</div>
                )}
                {[
                  ["Username", "username", "text", "e.g. jdoe"],
                  ["Email Address", "email", "email", "user@example.com"],
                  ["Password", "password", "password", "••••••••"],
                ].map(([label, field, type, placeholder]) => (
                  <div key={field}>
                    <label className="mb-1 block text-[13px] font-semibold text-ink-2">{label}</label>
                    <input
                      required
                      type={type}
                      value={signupForm[field]}
                      onChange={(e) => setSignupForm({ ...signupForm, [field]: e.target.value })}
                      placeholder={placeholder}
                      className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-white/15 dark:bg-white/5 dark:text-white"
                    />
                  </div>
                ))}
                <div>
                  <label className="mb-1 block text-[13px] font-semibold text-ink-2">System Role</label>
                  <select
                    value={signupForm.role}
                    onChange={(e) => setSignupForm({ ...signupForm, role: e.target.value })}
                    className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-[13.5px] text-ink outline-none focus:border-brand dark:border-white/15 dark:bg-white/5 dark:text-white"
                  >
                    <option value="ANALYST">Analyst (Read-only)</option>
                    <option value="ADMIN">Administrator</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-3 border-t border-line bg-paper-2 px-6 py-4 dark:border-white/10 dark:bg-white/5">
                <button
                  type="button"
                  onClick={() => setShowSignupModal(false)}
                  className="rounded-lg border border-line-strong bg-paper px-4 py-2 text-[13.5px] font-medium text-ink-2 transition-colors hover:bg-paper-3 dark:border-white/15 dark:bg-white/5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={signupBusy}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-[13.5px] font-semibold text-white transition-colors hover:bg-brand-hi disabled:opacity-60"
                >
                  {signupBusy && <FaSpinner className="animate-spin" />}
                  {signupBusy ? "Creating…" : "Create Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
