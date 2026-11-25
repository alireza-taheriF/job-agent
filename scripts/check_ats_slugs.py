import asyncio, httpx, sys, json
GH="adyen gitlab elastic cloudflare celonis n26 mollie miro contentful hellofresh getyourguide grafanalabs mongodb canonical grab agoda wise booking spotify bolt deliveryhero zalando trivago messagebird bunq picnic tomtom catawiki backbase mews pleo trustpilot unity veriff wolt glovo typeform revolut datadog sumup klarna shopify cohere".split()
LV="pipedrive wolt veriff bolt pleo personio tide palantir mistral binance kraken".split()
AS="deel supabase posthog linear n8n elevenlabs mistral cohere wolt multiverse synthesia poolside lovable photoroom pigment alan qonto doctolib".split()
async def main():
    ok={"greenhouse":[],"lever":[],"ashby":[]}
    async with httpx.AsyncClient(timeout=15) as c:
        async def g(s):
            r=await c.get(f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs"); return "greenhouse",s,r.status_code==200 and len(r.json().get("jobs",[]))>0
        async def l(s):
            r=await c.get(f"https://api.lever.co/v0/postings/{s}?mode=json"); return "lever",s,r.status_code==200 and isinstance(r.json(),list) and len(r.json())>0
        async def a(s):
            r=await c.get(f"https://api.ashbyhq.com/posting-api/job-board/{s}"); return "ashby",s,r.status_code==200 and len(r.json().get("jobs",[]))>0
        res=await asyncio.gather(*[g(s) for s in GH],*[l(s) for s in LV],*[a(s) for s in AS],return_exceptions=True)
    for x in res:
        if isinstance(x,tuple) and x[2]: ok[x[0]].append(x[1])
    print(json.dumps(ok))
asyncio.run(main())
