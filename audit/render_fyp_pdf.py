"""Render saved rehearsal PDFs for visual QA; no report or database changes."""
from pathlib import Path
import argparse
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw

parser=argparse.ArgumentParser()
parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent/'fyp-2026-11-04/flow-live')
directory=parser.parse_args().directory
for name in ('requirement','project'):
    doc=pdfium.PdfDocument(str(directory/f'{name}.pdf'))
    images=[]
    for index,page in enumerate(doc):
        file=directory/f'{name}-page-{index+1}.png'
        page.render(scale=1.2).to_pil().save(file)
        image=Image.open(file).convert('RGB');image.thumbnail((400,580))
        images.append(image)
    sheet=Image.new('RGB',(420*min(3,len(images)),620*((len(images)+2)//3)),'#ddd')
    draw=ImageDraw.Draw(sheet)
    for index,image in enumerate(images):
        x=(index%3)*420;y=(index//3)*620
        sheet.paste(image,(x+10,y+25));draw.text((x+10,y+5),f'{name} page {index+1}',fill='black')
    sheet.save(directory/f'{name}-contact-sheet.png')
    print(name,'pages',len(doc),'rendered')
