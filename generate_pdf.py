import os
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

pdf_filename = r"C:\Users\alain\.gemini\antigravity-ide\brain\f769f2df-c51b-42d1-85ca-c4889484d0d7\Carrossel_LinkedIn_EdgeAI_PNAAT.pdf"

# Page size: Square / Presentation Slide 800x800
page_width = 600
page_height = 600

def draw_background(canvas, doc):
    canvas.saveState()
    # Dark Navy Background
    canvas.setFillColor(colors.HexColor("#0B132B"))
    canvas.rect(0, 0, page_width, page_height, fill=True, stroke=False)
    
    # Accent top border
    canvas.setFillColor(colors.HexColor("#00E676")) # Emerald Green
    canvas.rect(0, page_height - 12, page_width, 12, fill=True, stroke=False)
    
    # Accent bottom border
    canvas.setFillColor(colors.HexColor("#1C2541"))
    canvas.rect(0, 0, page_width, 45, fill=True, stroke=False)
    
    # Footer text
    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(colors.HexColor("#8D99AE"))
    canvas.drawString(30, 18, "Alainy Rocha Gomes • Capacitação PNAAT (Softex / MCTI Futuro)")
    
    canvas.drawRightString(page_width - 30, 18, "Slide " + str(doc.page))
    canvas.restoreState()

doc = SimpleDocTemplate(
    pdf_filename,
    pagesize=(page_width, page_height),
    leftMargin=40,
    rightMargin=40,
    topMargin=40,
    bottomMargin=60
)

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'TitleStyle',
    fontName='Helvetica-Bold',
    fontSize=26,
    leading=32,
    textColor=colors.HexColor("#FFFFFF"),
    spaceAfter=15
)

subtitle_style = ParagraphStyle(
    'SubTitleStyle',
    fontName='Helvetica-Bold',
    fontSize=16,
    leading=22,
    textColor=colors.HexColor("#00E676"),
    spaceAfter=25
)

body_style = ParagraphStyle(
    'BodyStyle',
    fontName='Helvetica',
    fontSize=14,
    leading=22,
    textColor=colors.HexColor("#E0E6ED"),
    spaceAfter=12
)

badge_style = ParagraphStyle(
    'BadgeStyle',
    fontName='Helvetica-Bold',
    fontSize=12,
    leading=16,
    textColor=colors.HexColor("#00B4D8")
)

story = []

# --- SLIDE 1: CAPA ---
story.append(Spacer(1, 40))
story.append(Paragraph("CAPACITAÇÃO EM SISTEMAS EMBARCADOS & EDGE AI", title_style))
story.append(Paragraph("74 Horas de Formação Prática • PNAAT", subtitle_style))
story.append(Spacer(1, 20))
story.append(Paragraph("<font color='#00B4D8'><b>Instituição Emissora:</b></font> Softex / MCTI Futuro", body_style))
story.append(Paragraph("<font color='#00B4D8'><b>Foco:</b></font> Integração de Hardware, Eletrônica, IoT e Inteligência Artificial na Borda", body_style))
story.append(Spacer(1, 40))
story.append(Paragraph("<font color='#8D99AE'><i>Deslize para ver o detalhamento das trilhas ➔</i></font>", body_style))

# Page break for Slide 2
from reportlab.platypus import PageBreak
story.append(PageBreak())

# --- SLIDE 2: TRILHAS 1 & 2 ---
story.append(Spacer(1, 20))
story.append(Paragraph("TRILHAS 1 & 2: BASE DE HARDWARE", title_style))
story.append(Paragraph("Fundamentos em IoT & Eletrônica", subtitle_style))
story.append(Spacer(1, 10))
story.append(Paragraph("🔹 <b>Trilha de Fundamentos em IoT e Edge AI</b>", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Arquitetura de sistemas conectados e sensoriamento.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Conceitos de conectividade e transmissão de dados.", body_style))
story.append(Spacer(1, 15))
story.append(Paragraph("🔹 <b>Trilha de Eletrônica</b>", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Análise de circuitos e componentes eletrônicos.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Sinalização analógica e digital para automação.", body_style))

story.append(PageBreak())

# --- SLIDE 3: TRILHA EMBARCADOS ---
story.append(Spacer(1, 20))
story.append(Paragraph("TRILHA 3: SISTEMAS EMBARCADOS", title_style))
story.append(Paragraph("Microcontroladores & Firmware", subtitle_style))
story.append(Spacer(1, 15))
story.append(Paragraph("🔹 <b>Trilha de Embarcados (16 horas)</b>", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Programação de microcontroladores de baixo consumo.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Protocolos de comunicação industrial (SPI, I2C, UART).", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Gerenciamento de memória e periféricos em hardware.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Desenvolvimento de firmware robusto e otimizado.", body_style))

story.append(PageBreak())

# --- SLIDE 4: TRILHA EDGE AI ---
story.append(Spacer(1, 20))
story.append(Paragraph("TRILHA 4: INTELIGÊNCIA ARTIFICIAL NA BORDA", title_style))
story.append(Paragraph("Edge AI & Machine Learning", subtitle_style))
story.append(Spacer(1, 15))
story.append(Paragraph("🔹 <b>Trilha de Edge AI (28 horas)</b>", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Implantação de modelos de IA diretamente no hardware.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Otimização para baixa latência e consumo energético reduzido.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Autonomia local sem dependência constante de nuvem.", body_style))
story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• Privacidade e segurança no processamento de dados na ponta.", body_style))

story.append(PageBreak())

# --- SLIDE 5: CONCLUSÃO ---
story.append(Spacer(1, 20))
story.append(Paragraph("CAPACITAÇÃO CONCLUÍDA", title_style))
story.append(Paragraph("Resumo da Certificação Global (74h)", subtitle_style))
story.append(Spacer(1, 10))
story.append(Paragraph("🏆 <b>Capacitação em Sistemas Embarcados e IA na Borda</b>", body_style))
story.append(Paragraph("✅ <b>Programa:</b> PNAAT (Programa Nacional de Aprendizado Acelerado em Tecnologia)", body_style))
story.append(Paragraph("✅ <b>Apoio:</b> Softex • MCTI Futuro • Ministério da Ciência e Tecnologia", body_style))
story.append(Paragraph("✅ <b>Status:</b> Concluído com Sucesso", body_style))
story.append(Spacer(1, 35))
story.append(Paragraph("<font color='#00E676'><b>Vamos conectar hardware e Inteligência Artificial?</b></font>", body_style))

doc.build(story, onFirstPage=draw_background, onLaterPages=draw_background)
print("PDF gerado com sucesso!")
