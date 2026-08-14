# Sleeping and waking

The app scales to zero after five idle minutes. The next request then waits for
Azure to start a replica. This document is what to do if that wait stops being
acceptable.

Nothing here needs to be done. The site works as it is; this is a cost dial with
a latency reading on it.

## What the wait is made of

Measured against production on 2026-08-13, from the replica lifecycle events,
*after* the probe and image work:

| Phase | Time | Whose |
|---|---|---|
| Scheduling the replica onto a node | 2-3s | Azure |
| Pulling the image | ~4s | Azure, and not much a smaller image changes |
| Creating the container | 6-11s | Azure, and variable |
| nginx and gunicorn up and listening | <1s | ours |
| Routing the queued request to the ready replica | 4-13s | Azure |

The application is up and serving under a second after its container starts.
Django is a rounding error in this. Everything else is the platform.

**A cold start cannot be made to feel fast. It can only be avoided.** But a
surprising amount of it turned out to be self-inflicted, so measure before
believing any attribution here — including the ones below, which replaced two
earlier attributions that were wrong.

### The probes cost far more than they look like they should

Measured by deploying this same image to throwaway container apps in this
environment that differed *only* in their probes, timing container start to
first served request:

| Probes defined | Container start → served |
|---|---|
| Startup only | 4.4s |
| Startup + Readiness | 8.2s |
| Startup + Readiness + Liveness (`initialDelaySeconds: 10`) | 15.9s |
| Startup + Readiness + Liveness (`initialDelaySeconds: 1`) | 9.5s |

Defining a probe delays the platform routing to the replica well past the point
the replica is answering. In the third case nginx returned 200 to health probes
continuously for **fourteen seconds** while the client's request was still
queued upstream — the container was up, healthy, and idle, and the request was
somewhere in Azure's ingress.

The mechanism is not visible from outside Azure. What is visible is the cost, so
the settings are chosen against these numbers:

- **Liveness `initialDelaySeconds: 1`, not 10.** Worth 7.7s. A liveness probe
  does not run until the startup probe has succeeded, so delaying it protects
  nothing the startup probe is not already protecting. This is the single
  largest saving in the whole exercise.
- **Readiness asks nginx, not Django.** The startup probe has already
  established that Django serves, and that only has to be true once.

### What did not work, measured in production

Two changes that the controlled experiments predicted would help, and did not.
Recorded because the reasoning was sound and the result still came out flat, and
because the next person will otherwise have the same two ideas.

| | Predicted | Delivered |
|---|---|---|
| Image 528MB → 476MB (156 → 111MB compressed) | 4-6s | ~0.1s |
| Probes reduced to startup only | ~5s | ~0 |

**Image size does not drive container creation in the range that matters.** The
hello-world test showed 2.1s creation at ~20MB against 6-11s at 528MB, which
looked like a straight line worth riding down. It is not one: 476MB and 528MB
both create in ~10.4s. Something else dominates above some threshold, and 50MB
either way is beneath it.

**The probe result did not transfer from the scratch apps.** A throwaway app
with a startup probe alone served 4.4s after container start; production with
the same probe configuration takes ~12.8s. The scratch apps had no volume
mounts, no secrets, no database, and had just been created. They measured
something real about themselves and predicted nothing about production.

Both changes are still in place — a smaller image and less configuration are
worth having on their own terms — but neither is a cold-start fix, and the
totals below have not moved:

| Date | Change | Cold start |
|---|---|---|
| 2026-08-13 | baseline | 42s |
| 2026-08-13 | probes on `/readyz`, slimmer image, `--preload` | 38.7s |
| 2026-08-13 | startup probe timeout + wsgi warm-up | 33.0s |
| 2026-08-13 | liveness `initialDelaySeconds` 10 → 1 | 27.8s |
| 2026-08-14 | image slimming + startup probe only | 29.1s |

The lesson worth keeping: of everything tried, only the probe *timing* work
moved the number, and it moved it once. Everything after that has been flat.
**Assume the remaining time is Azure's until a measurement says otherwise, and
do not spend effort against a projection that has not been measured in
production.**

### Volume mounts cost nothing measurable

Worth recording, because the opposite is the intuitive guess and acting on it
would mean moving document storage off Azure Files onto blob or S3 — real work
for no latency gain.

Same method, adding the two Azure Files shares as the only difference:

| Variant | Mounts | Probes | Start → served |
|---|---|---|---|
| Mountless | none | Startup + Readiness | 8.2s |
| **Mounted** | **media + published** | production's set | **9.5s** |

Roughly a second apart, and the mounted one started clean with no probe failures
at all. The phase between image pull and container start — the one that *looks*
like mounting, sitting where it does in the timeline — varies 6-11s whether two
shares are attached or none.

What does vary that much is which node the replica lands on. The same
configuration measured 22.6s and 27.8s in consecutive runs, the difference being
container creation (7.8s vs 10.5s) and whether the first probe caught nginx
listening. **Treat any single cold-start measurement as ±5s**, and do not
conclude anything from one run — including from the numbers above, each of which
is one run.

Storage portability is a fine reason to move off Azure Files, and
[`apps/core/storage.py`](../backend/apps/core/storage.py) already has the
abstraction with a complete S3 backend behind it. Cold start is not.

### The probe-timeout trap

Worth knowing if you ever touch the probes: **Container Apps caps a probe's
effective timeout at its `periodSeconds`, whatever `timeoutSeconds` says.** A
startup probe configured with `periodSeconds: 1, timeoutSeconds: 2` logs
`Probe of StartUp failed with timeout in 1 seconds`.

That turned polling *faster* into starting *slower*. Django's first request
builds the URL resolver and middleware chain lazily, which takes more than a
second on a cold replica, so each probe cut the request off before it finished
and tried again — five times, six seconds, with the app sitting there able to
answer.

Two changes fixed it, and both are worth keeping:

- The startup probe polls every 3s, so each attempt gets 3s to answer.
- [`config/wsgi.py`](../backend/config/wsgi.py) drives one synthetic request at
  import time, under gunicorn's `--preload`, so the lazy initialization happens
  in the master before any probe arrives and every forked worker inherits it.

## Avoiding it: keep a replica warm

```bash
MIN_REPLICAS=1 ./scripts/deploy_azure_containerapps.sh
```

That is the whole change. `MIN_REPLICAS` defaults to `0`, and the deploy script
passes it through to the rendered app spec.

### What it costs

A replica held at the minimum replica count and not serving requests bills at
Azure's *idle* rate. Azure's conditions for idle: all containers started, no
HTTP request in flight, under 0.01 vCPU, and under 1,000 bytes/second of
network traffic. An idle Django replica sits well inside that.

Retail rates for `centralus`, fetched 2026-08-13 — check them again before
relying on the total, with:

```bash
curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName%20eq%20'Azure%20Container%20Apps'%20and%20armRegionName%20eq%20'centralus'" \
  | python3 -m json.tool | grep -A2 Idle
```

| Meter | Active | Idle |
|---|---|---|
| vCPU | $0.000024/s | **$0.000003/s** (8× cheaper) |
| Memory | $0.000003/GiB-s | $0.000003/GiB-s (no discount) |

At the current 1 vCPU / 2 GiB, held warm for a full 30-day month:

```
vCPU     2,592,000 s      × $0.000003          =  $7.78
memory   5,184,000 GiB-s  × $0.000003          = $15.55
                                                 ------
                                                 $23.33
less the monthly free grant                      -$1.62
                                                 ------
                                                 ~$21.71/month
```

Memory is the larger half and gets no idle discount, which is worth knowing if
the container is ever resized: dropping to 1 GiB would save more than dropping
to half a vCPU.

## Avoiding it only when it matters: business hours

Advocates use this on weekday working hours. Paying to stay warm through nights
and weekends buys nothing. Warm for 12 hours × 5 days is about 260 hours of the
month's 730, or roughly **$7.70/month** on the same rates.

There is no built-in schedule for this — Container Apps has no "scale schedule"
on the Consumption plan — so it is two scheduled commands. Either of these
works; neither needs a code change.

### With a GitHub Actions schedule

Add a workflow that flips the minimum. It needs the same
`AZURE_CLIENT_ID`/`TENANT_ID`/`SUBSCRIPTION_ID` secrets the deploy workflow
already uses.

```yaml
name: Warm hours

on:
  schedule:
    # Times are UTC. 11:00 UTC = 07:00 America/New_York during EDT.
    # GitHub does not adjust for daylight saving: over the winter these
    # land an hour later locally unless you shift them.
    - cron: "0 11 * * 1-5"   # weekday morning: warm
    - cron: "0 23 * * 1-5"   # weekday evening: let it sleep

permissions:
  id-token: write

jobs:
  set-minimum:
    runs-on: ubuntu-latest
    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Set the minimum replica count
        run: |
          # 11:00 warms it; anything else puts it back to sleep.
          MIN=0
          [ "${{ github.event.schedule }}" = "0 11 * * 1-5" ] && MIN=1
          az containerapp update -g agentic-housing-rg -n agentic-housing-app \
            --min-replicas "$MIN" -o none
          echo "min-replicas set to $MIN"
```

Two things to know before relying on it. Scheduled workflows are queued, not
guaranteed on the minute — GitHub delays them under load, sometimes by tens of
minutes, so the first advocate in may still meet a cold start. And a scheduled
workflow is disabled automatically after 60 days without repository activity.

### With an Azure automation schedule

More reliable timing, and it stays inside Azure. Create two
[Logic App](https://learn.microsoft.com/azure/logic-apps/) recurrence triggers,
or an Automation Account runbook on a schedule, each running one line:

```bash
az containerapp update -g agentic-housing-rg -n agentic-housing-app --min-replicas 1   # morning
az containerapp update -g agentic-housing-rg -n agentic-housing-app --min-replicas 0   # evening
```

Whichever you pick, give the identity running it the **Container Apps
Contributor** role on the resource group and nothing wider.

### Careful: the deploy script will undo it

`scripts/deploy_azure_containerapps.sh` applies a full app spec, so it resets
`minReplicas` to whatever `MIN_REPLICAS` says — default `0`. If a schedule is
running, a configuration deploy at 2pm silently puts the app back to sleep until
the next morning's trigger. Either run the deploy with `MIN_REPLICAS=1` during
warm hours, or re-run the warming command afterwards.

Merging to `main` is safe: that workflow only updates the image and leaves scale
alone.

## What the app does in the meantime

While the container is asleep it cannot say so — `index.html` is served by the
nginx inside that same container, so a cold first page load is a blank wait with
nothing available to explain it. Fixing that needs something warm in front of
the app: a CDN or a Cloudflare Worker on `cle-draft.lemmalegal.com` serving the
shell and letting the SPA wait on the API. That is a real option, and a bigger
change than this document covers.

What the frontend does handle is the case that actually bites: a tab left open
past the idle timeout, where the next click would otherwise hang with no
explanation. [`frontend/src/api/wakeNotice.js`](../frontend/src/api/wakeNotice.js)
watches for a request that has been out for more than 1.2s and then asks
`/healthz` — which a running container answers off nginx in milliseconds. Only
if *that* goes unanswered does it conclude nothing is serving and show the
notice. Checking whether the server answers at all, rather than timing the
request, is what keeps the notice off the long drafting and chat calls, which
are slow while the server is perfectly awake.
