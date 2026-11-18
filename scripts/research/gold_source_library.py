"""Keep local copies of the public source material cited in the market atlas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json

from lxml import html
import requests
from scripts.research.collect_gold_ticks import ROOT, STORE, sha


def save(record):
    url = record["url"]
    try:
        response = requests.get(url, timeout=(10,35))
        response.raise_for_status()
        if response.content.startswith(b"%PDF"):
            data, extension = response.content, "pdf"
            scope = "original PDF"
        else:
            if url.lower().endswith(".pdf"):
                raise ValueError("Document link returned a non-PDF response")
            tree = html.fromstring(response.content)
            for node in tree.xpath("//script|//style|//nav|//footer|//noscript"):
                node.drop_tree()
            roots = tree.xpath("//article|//main")
            node = roots[0] if roots else tree
            body = "\n".join(x.strip() for x in node.itertext() if x.strip())
            if len(body.strip())<400 or "verify you are human" in body[:1500].lower():
                raise ValueError("No usable public page text")
            data, extension = body.encode("utf-8"), "txt"
            scope = ("publisher access notice only" if "Please sign in or register for full access" in body[:180]
                     else "extracted public page text")
        path = STORE/"payload/literature"/(record["id"]+"."+extension)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        return dict(**record,status="stored",content_scope=scope,final_url=response.url,
                    path=path.relative_to(STORE).as_posix(),bytes=len(data),sha256=sha(path))
    except (requests.RequestException,OSError,ValueError) as exc:
        return dict(**record,status="unavailable",reason=str(exc))


def main():
    notes = json.loads((ROOT/"research/results/finalization_2026-11-18/literature.json").read_text())
    items = [{k:r[k] for k in ("id","title","url")} for r in notes["records"]]
    items.extend(dict(id=key,title=title,url=url) for key,title,url in [
        ("L12","Intraday price pressure and order flow around US Treasury auctions","https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1188.pdf"),
        ("V01","Exness historical quote feed","https://www.exness.com/tick-history/"),
        ("V02","Precious metal benchmark auctions","https://www.lbma.org.uk/prices-and-data/lbma-precious-metal-prices"),
        ("V03","Shanghai gold benchmark contract specification","https://en.sge.com.cn/upload/file/201703/24/RGDmtsfPVEzy935O.pdf"),
        ("V04","CFTC release schedule","https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm"),
        ("V05","Philadelphia Fed real-time macro vintages","https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists"),
    ])
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(save,items))
    result = dict(captured_utc=datetime.now(timezone.utc).isoformat(),records=records)
    (STORE/"literature_catalog.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print([(r["id"],r["status"]) for r in records])


if __name__=="__main__":
    main()
