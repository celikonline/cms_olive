from html.parser import HTMLParser
import json
from pathlib import Path

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.capture=False; self.texts=[]; self.images=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='script' and a.get('id')=='__NEXT_DATA__': self.capture=True
        if tag=='img': self.images.append(a)
        if tag=='a': self.links.append(a.get('href'))
    def handle_data(self,data):
        if self.capture:
            Path('reference-data.json').write_text(json.dumps(json.loads(data),ensure_ascii=False,indent=2),encoding='utf-8'); self.capture=False
        elif data.strip() and len(data)<600: self.texts.append(data.strip())

p=Parser(); p.feed(Path('reference.html').read_text(encoding='utf-8'))
Path('reference-summary.json').write_text(json.dumps({'texts':p.texts,'images':p.images,'links':p.links},ensure_ascii=False,indent=2),encoding='utf-8')
print('Saved reference data:',len(p.images),'images,',len(set(p.links)),'links')
