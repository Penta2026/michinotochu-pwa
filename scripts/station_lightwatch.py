#!/usr/bin/env python3
"""Conservative station feed change watcher; never publishes events."""
import argparse, hashlib, json, time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
JST=timezone(timedelta(hours=9))
def load(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError: return default
def host_ok(url, hosts):
    try:
        u=urlparse(url)
        return u.scheme=="https" and u.hostname in hosts and not u.username and not u.password and u.port is None
    except ValueError: return False
def verified_sources(rules):
    out=[]
    for s in rules.get("sources",[]):
        url=s.get("listingUrl","")
        if not s.get("enabled",True) or s.get("articleMode") or not host_ok(url,s.get("allowedHosts",[])): continue
        out.append({"id":s["id"],"prefecture":s["prefecture"],"roadName":s["roadName"],"url":url})
    return out
def slot_for(station_id,days):
    return int(hashlib.sha256(station_id.encode()).hexdigest()[:8],16)%days
def fetch(url, old, timeout):
    hdr={"User-Agent":"MichinotochuRoadEventWatch/0.1","Accept":"text/html, application/xml, text/xml"}
    if old.get("etag"): hdr["If-None-Match"]=old["etag"]
    if old.get("modified"): hdr["If-Modified-Since"]=old["modified"]
    try:
        with urlopen(Request(url,headers=hdr),timeout=timeout) as response:
            dest=urlparse(response.geturl()); original=urlparse(url)
            if dest.scheme!="https" or dest.hostname!=original.hostname: return {"status":"redirect_review_required"}
            kind=response.headers.get("Content-Type","").lower()
            if not any(v in kind for v in ("text/html","xml","rss")): return {"status":"unsupported_content"}
            raw=response.read(524289)
            if len(raw)>524288: return {"status":"oversized_page"}
            h=hashlib.sha256(raw).hexdigest()
            return {"status":"changed" if old.get("sha256") and old["sha256"]!=h else "unchanged" if old.get("sha256") else "first_seen",
                    "sha256":h,"etag":response.headers.get("ETag",""),"modified":response.headers.get("Last-Modified","")}
    except HTTPError as ex:
        if ex.code==304: return {"status":"unchanged","sha256":old.get("sha256",""),"etag":old.get("etag",""),"modified":old.get("modified","")}
        return {"status":"http_error","httpCode":ex.code}
    except (TimeoutError,OSError,URLError) as ex: return {"status":"fetch_error","errorType":type(ex).__name__}
def run(args):
    stations=load(DATA/"station_coverage_registry.json",{}).get("stations",[])
    if len(stations)!=1234: raise ValueError("Expected 1234 station records")
    feeds=verified_sources(load(DATA/"station_event_discovery_sources.json",{}))
    statefile=DATA/"station_lightwatch_state.json"
    old=load(statefile,{"sources":{}}).get("sources",{})
    now=datetime.now(JST)
    slot=now.date().toordinal()%args.cycle_days
    active=[s for s in stations if slot_for(s["id"],args.cycle_days)==slot]
    targets={(s["prefecture"],s["roadName"]) for s in active}
    due=feeds if args.daily_verified else [s for s in feeds if (s["prefecture"],s["roadName"]) in targets]
    result=[]; state=dict(old); touched={}
    if args.fetch:
        for item in due[:args.max_requests]:
            host=urlparse(item["url"]).hostname
            wait=args.host_delay-(time.monotonic()-touched.get(host,-1e9))
            if wait>0: time.sleep(wait)
            touched[host]=time.monotonic()
            reply=fetch(item["url"],old.get(item["id"],{}),args.timeout)
            result.append({**item,"status":reply["status"]})
            if reply["status"] in ("changed","first_seen","unchanged"):
                state[item["id"]]={**reply,"checkedAt":now.isoformat()}
    report={"generatedAt":now.isoformat(),"mode":"fetch" if args.fetch else "dry_run",
            "cycleDays":args.cycle_days,"stationsTotal":len(stations),"stationsScheduledToday":len(active),
            "verifiedListingSources":len(feeds),"verifiedDueToday":len(due),
            "requestsAttempted":len(result),"statusCounts":dict(Counter(x["status"] for x in result)),
            "newOrChanged":[x for x in result if x["status"] in ("changed","first_seen")],
            "limitations":["Changes are NOT verified events or automatically published.",
                           "Unverified official-site candidates are not fetched.","No events found never means none exist."]}
    (DATA/"station_lightwatch_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.fetch: statefile.write_text(json.dumps({"sources":state},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fetch",action="store_true")
    p.add_argument("--daily-verified",action="store_true")
    p.add_argument("--cycle-days",type=int,default=7)
    p.add_argument("--max-requests",type=int,default=40)
    p.add_argument("--host-delay",type=float,default=2.0)
    p.add_argument("--timeout",type=float,default=10.0)
    a=p.parse_args()
    if a.cycle_days<1 or a.max_requests<1 or a.host_delay<1 or a.timeout<=0: p.error("Invalid limits")
    run(a)
if __name__=="__main__": main()
