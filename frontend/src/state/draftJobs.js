// Draft generation runs in the background; the server answers with a job and
// this waits for it. Held open as one request, generation outlived the proxy's
// timeout and reached the advocate as "Failed to fetch" while the draft was
// being saved anyway -- see apps/drafting/generation_jobs.py.

const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// `response` is what POST .../drafts/ answered; `poll(jobId)` fetches the job.
// Resolves to the drafts, or throws the job's own error.
export async function waitForDrafts(response, poll, { interval = 2000, sleep = defaultSleep, onProgress } = {}) {
  if (response?.drafts) return response.drafts;
  let job = response?.job;
  if (!job) throw new Error("The server did not start generating the draft.");
  for (;;) {
    onProgress?.(job);
    if (job.status === "complete") {
      const finished = job.drafts ? job : await poll(job.id);
      return finished.drafts || [];
    }
    if (job.status === "failed") throw new Error(job.error || "The draft could not be generated.");
    await sleep(interval);
    const next = await poll(job.id);
    if (next.job?.status === "complete" && next.drafts) return next.drafts;
    job = next.job;
  }
}
