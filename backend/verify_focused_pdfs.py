"""Synthetic short/long PDF rendering; no real accounts or database opened."""
import json
import logging
from pathlib import Path
from pypdf import PdfReader
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from test_integrated_reporting import IntegratedReportingTests

logging.disable(logging.CRITICAL)
out = Path('../audit/focused-pdf')
out.mkdir(parents=True, exist_ok=True)
IntegratedReportingTests.setUpClass()
fixture = IntegratedReportingTests()
fixture.setUp()
try:
    for kind in ('short', 'long'):
        if kind == 'long':
            fixture.f.sql('UPDATE requirements SET reviewer_notes=? WHERE id=?',
                          ('Synthetic detailed review <safe> & plain text. ' * 350 + 'END-LONG-REVIEW', fixture.r['id']))
            fixture.f.sql('UPDATE requirements SET description=? WHERE id=?',
                          ('Synthetic long source with documented actor and observable result.\n' * 130 + 'END-LONG-SOURCE', fixture.r['id']))
        response = fixture.engineer.get(f'/api/requirements/{fixture.r["id"]}/report.pdf')
        assert response.status_code == 200
        filename = out / f'{kind}.pdf'
        filename.write_bytes(response.data)
        reader = PdfReader(filename)
        text = '\n'.join(page.extract_text() for page in reader.pages)
        if kind == 'long':
            assert 'END-LONG-REVIEW' in text and 'END-LONG-SOURCE' in text
        document = pdfium.PdfDocument(filename)
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=1.2)
            bitmap.to_pil().save(out / f'{kind}-{index+1}.png')
            bitmap.close()
            page.close()
        for start in range(0, len(document), 6):
            sheet = Image.new('RGB', (960, 2040), '#d8cec0')
            draw = ImageDraw.Draw(sheet)
            for index in range(start, min(start+6, len(document))):
                image = Image.open(out / f'{kind}-{index+1}.png')
                image.thumbnail((460, 650))
                x, y = ((index-start)%2)*480+10, ((index-start)//2)*680+23
                sheet.paste(image, (x,y))
                draw.text((x,y-18), f'{kind} page {index+1}', fill='black')
            sheet.save(out / f'{kind}-sheet-{start//6+1}.png')
        document.close()
        print(json.dumps(dict(report=kind, pages=len(reader.pages), all_pages_rendered=True, last_marker_present=kind=='long')))
finally:
    fixture.doCleanups()
