import os
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

def generate_pdf(output_path: str, diagram_path: str, capacity_model_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=LETTER, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []
    # Title
    elements.append(Paragraph('GraphOne Ingestion Pipeline Architecture', styles['Heading1']))
    elements.append(Spacer(1, 12))
    # Diagram
    if os.path.exists(diagram_path):
        img = Image(diagram_path, width=500)
        elements.append(img)
        elements.append(Spacer(1, 12))
    # Capacity model (as text)
    if os.path.exists(capacity_model_path):
        with open(capacity_model_path, 'r', encoding='utf-8') as f:
            cm = f.read()
        elements.append(Paragraph('Capacity Model', styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(cm.replace('\n', '<br/>'), styles['Normal']))
    doc.build(elements)
    print('PDF generated at', output_path)

if __name__ == '__main__':
    out_pdf = os.path.abspath(os.path.join('docs', 'ARCHITECTURE.pdf'))
    diagram = os.path.abspath(os.path.join('docs', 'architecture_diagram_kafka.png'))
    capacity = os.path.abspath(os.path.join('docs', 'CAPACITY_MODEL.md'))
    generate_pdf(out_pdf, diagram, capacity)
