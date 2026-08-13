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
| Scheduling the replica onto a node | 3.2s | Azure |
| Pulling the image | 4.6s | Azure |
| Creating the container and mounting shares | 10.6s | Azure |
| nginx and gunicorn up and listening | ~1s | ours |
| Startup probe getting a passing answer | ~6s | ours, since fixed |
| Ingress actually routing to the ready replica | ~14s | Azure |
| **Total** | **38.7s** | |

The honest summary: **about 30 of those 38 seconds are Azure's and cannot be
tuned from this repository.** The application is up and serving one second after
its container starts. Everything before that is scheduling, pulling and
mounting; the fourteen seconds after the replica reports ready is Container Apps
propagating the endpoint to its ingress.

This is worth stating plainly because the intuition is wrong. Before measuring
it looked like most of the delay was Django starting, and it is not: Django is
a rounding error here. Tuning the app bought about three seconds, and a further
five came from a mistake this exercise created and then fixed (below). The
remaining floor is roughly 30 seconds and it is structural.

**A cold start cannot be made to feel fast. It can only be avoided.**

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
