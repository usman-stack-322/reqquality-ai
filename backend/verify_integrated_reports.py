"""Generate and render synthetic integration reports; never opens a workstation DB."""
import json
import logging
from pathlib import Path
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image,ImageDraw
from test_integrated_reporting import IntegratedReportingTests

logging.disable(logging.CRITICAL)
output=Path(__file__).resolve().parents[1]/'audit/integrated-pdf'
output.mkdir(parents=True,exist_ok=True)
IntegratedReportingTests.setUpClass()
case=IntegratedReportingTests();case.setUp()
try:
    failed=case.run_case('Fail');case.create_bug(failed);case.run_case('Pass');case.approve()
    case.edit_source('Customers can view the subject and description of tickets they own.')
    for name,path in (('requirement',f'/api/requirements/{case.r["id"]}/report.pdf'),('project','/api/reports/project.pdf')):
        response=case.engineer.get(path);assert response.status_code==200
        filename=output/(name+'.pdf');filename.write_bytes(response.data)
        reader=PdfReader(filename)
        text='\n'.join(page.extract_text() for page in reader.pages)
        assert 'BUG-' in text and 'Version-bound SQA review history' in text
        document=pdfium.PdfDocument(filename)
        sheets=[]
        for start in range(0,len(document),6):
            sheet=Image.new('RGB',(640,3*470),'#d8cec0');draw=ImageDraw.Draw(sheet)
            for index in range(start,min(start+6,len(document))):
                page=document[index];bitmap=page.render(scale=1.25)
                image=bitmap.to_pil();image.thumbnail((310,438))
                x=((index-start)%2)*320+5;y=((index-start)//2)*470+22
                sheet.paste(image,(x,y));draw.text((x,y-18),f'{name} page {index+1}',fill='black')
                bitmap.close();page.close()
            sheet_path=output/f'{name}-sheet-{start//6+1}.png';sheet.save(sheet_path);sheets.append(sheet_path.name)
        document.close()
        print(json.dumps(dict(report=name,pages=len(reader.pages),rendered_all_pages=True,sheets=sheets)))
finally:case.doCleanups()
