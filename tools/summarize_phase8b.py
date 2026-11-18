"""Create additional redacted report copies; never overwrite raw historical evidence."""
from collections import Counter
import json
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def redact(value):
    value=value.replace(str(ROOT).replace('\\','\\\\'),'<WORKSPACE>').replace(str(ROOT),'<WORKSPACE>')
    value=re.sub(r'(?i)C:\\+Users\\+[^\\\s<>"\']+', '<USERPROFILE>', value)
    value=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_.~+/=-]+',r'\1<REDACTED>',value)
    value=re.sub(r'(?i)(postgresql(?:\+psycopg)?://)[^\s/@]+:[^\s/@]+@',r'\1<REDACTED>@',value)
    return value


def main(label):
    if not label.replace('_','').isalnum():raise ValueError('Report label required')
    folder=ROOT/'docs/PHASE8B_TESTS'/label
    status=json.loads((folder/'exit.json').read_text(encoding='utf8'))
    tree=ET.parse(folder/'results.xml');root=tree.getroot()
    for node in root.iter():
        node.attrib.pop('hostname',None)
        node.attrib={k:redact(v) for k,v in node.attrib.items()}
        if node.text:node.text=redact(node.text)
        if node.tail:node.tail=redact(node.tail)
    suites=list(root.iter('testsuite'));tests=list(root.iter('testcase'))
    summary={k:sum(int(s.attrib.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    summary['passed']=summary['tests']-summary['failures']-summary['errors']-summary['skipped']
    summary.update({k:status[k] for k in ('exit_code','started_at','finished_at','source_unchanged_during_run','demo_fingerprint_unchanged','head')})
    summary['by_module']=dict(Counter(n.attrib['classname'] for n in tests))
    for path,content in (
        (folder/'results.redacted.xml',ET.tostring(root,encoding='unicode')),
        (folder/'run.redacted.log',redact((folder/'run.log').read_text(encoding='utf8'))),
        (folder/'summary.public.json',json.dumps(summary,indent=2))):
        with path.open('x',encoding='utf8') as f:f.write(content)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main(sys.argv[1])
