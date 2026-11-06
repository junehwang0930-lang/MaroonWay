"""Read a PDF and write a unique investigation CSV; never open or migrate a DB."""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pipeline import parse_pages,read_pdf_pages,validate_metadata
from gpa_review import assess_gpa


def generate_report(pdf, output, *, year=2026, semester='SPRING', college='AT', college_name='Arts & Sciences', include_sections=(), review_csv=None):
    content=Path(pdf).read_bytes()
    pages=read_pdf_pages(content)
    metadata=validate_metadata(pages,year=year,semester=semester,college=college,college_name=college_name)
    parsed,rejected=parse_pages(pages)
    digest=hashlib.sha256(content).hexdigest()
    historical={}
    if review_csv:
        with Path(review_csv).open(encoding='utf-8-sig',newline='') as handle:
            for index,item in enumerate(csv.DictReader(handle),1):
                expected={'term':metadata.term,'college':metadata.college,'source_sha256':digest}
                for field,value in expected.items():
                    if item.get(field) and item[field] != value:
                        raise ValueError(f'Review CSV {field} does not match the selected PDF at item {index}')
                association='verified' if all(item.get(k)==v for k,v in expected.items()) else 'unverified'
                historical.setdefault(item.get('section_code',''),[]).append((index,item.get('issue',''),association))
    findings=[]
    now=datetime.now(timezone.utc).isoformat()
    digest=hashlib.sha256(content).hexdigest()
    for row in parsed:
        code=f'{row.subject}-{row.number}-{row.section}'
        record=asdict(row);record['gpa_reported']=row.gpa
        result=assess_gpa(record)
        status=result['gpa_review_status']
        if status=='matches_reported' and code not in include_sections and code not in historical:
            continue
        items=historical.get(code) or [(1,'GPA comparison','not_applicable')]
        for number,issue,association in items:
            findings.append(dict(term=metadata.term,college=metadata.college,subject=row.subject,course_number=row.number,section=row.section,source_page=row.source_page,gpa_reported=row.gpa,gpa_calculated=result['gpa_calculated'],gpa_difference=result['gpa_difference'],af_total=row.af_total,review_status=status,review_note=result['gpa_review_note'],evidence=json.dumps(dict(source_pdf_sha256=digest,source_page=row.source_page,official_cause_evidence=result['gpa_review_evidence']),ensure_ascii=False),review_item_number=number,review_item=issue,review_association=association,investigation_complete=False,reviewed_at=now,credit_type='unknown',credit_hours='',a=row.a,b=row.b,c=row.c,d=row.d,f=row.f,source_sha256=digest,source_url=metadata.source_url,raw_row=row.raw_row))
    for number,(page,code,issue,raw) in enumerate(rejected,1):
        parts=code.split('-',2)
        findings.append(dict(term=metadata.term,college=metadata.college,subject=parts[0],course_number=parts[1] if len(parts)>1 else '',section=parts[2] if len(parts)>2 else '',source_page=page,review_status='unexplained_mismatch',review_note='Parsing rejected; source versus parser cause has not been established',evidence='[]',review_item_number=number,review_item=issue,investigation_complete=False,reviewed_at=now,credit_type='unknown',source_sha256=digest,source_url=metadata.source_url,raw_row=raw))
    findings.sort(key=lambda r:(r.get('gpa_difference') is None,-(r.get('gpa_difference') or 0),r['subject'],r['course_number'],r['section'],r['review_item_number']))
    fields=['term','college','subject','course_number','section','source_page','gpa_reported','gpa_calculated','gpa_difference','af_total','review_status','review_note','evidence','review_item_number','review_item','review_association','investigation_complete','reviewed_at','credit_type','credit_hours','a','b','c','d','f','source_sha256','source_url','raw_row']
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    target=output/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex+'.csv')
    with target.open('x',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(findings)
    return target,len(findings)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'data/gpa_investigations')
    parser.add_argument('--year',type=int,default=2026)
    parser.add_argument('--semester',choices=['SPRING','FALL'],default='SPRING')
    parser.add_argument('--college',default='AT');parser.add_argument('--college-name',default='Arts & Sciences')
    parser.add_argument('--include-section',action='append',default=[])
    parser.add_argument('--review-csv',type=Path)
    args=parser.parse_args()
    target,count=generate_report(args.pdf,args.output,year=args.year,semester=args.semester,college=args.college,college_name=args.college_name,include_sections=args.include_section,review_csv=args.review_csv)
    print(f'{count} investigation items; no database changes. CSV: {target}')

if __name__=='__main__':main()
