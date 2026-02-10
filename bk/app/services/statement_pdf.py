"""
FLC Bank - Serviço de Geração de PDF de Extrato
Gera extrato bancário em PDF com logo e formatação profissional
"""

from io import BytesIO
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import base64


class StatementPDFGenerator:
    """Gerador de PDF de extrato bancário."""
    
    # Logo FLC Bank em base64 (um simples placeholder dourado)
    LOGO_BASE64 = """
    iVBORw0KGgoAAAANSUhEUgAAAMgAAAAyCAYAAAAZUZThAAAACXBIWXMAAAsTAAALEwEAmpwYAAAF
    z0lEQVR4nO2dW4hVVRjHf+OMl5lxHBu8pJZNZpSlhUVFJpRddKxIpZeCLmBFD0F0oa4PQQ9RDxYU
    PRTRS0UvXaiosCKKCqKiC1lkZWWZmo06OuOoMzoPP9ZhO8fZe++191577zn/H2zmnL3XXt/6Lmuv
    9a21RoGJiYmJiYmJSTbI4bKPuKIB6I+8Pwp4OmK6JkUQqwC9gceB24CfgdvdU9K0BLgBOBh4C3gc
    eCpCmiZFEPdX1QU4B9gb+A14CpgbIV0DZQywO/Ax8DwwLUJ6BsoYYDdgGfAiMD1Cegqg0Q8Cegj4
    DHgxQnoKoLEd8CLwMjA7QnoKoNH2wAvAK8CcCOkpgEa7BXgZeJXod0kB7Ae8ALxG9LukAPYGngde
    J/pdUgB7Ac8CbxD9LimAvYCngDeBhyKkJ9fYD3gaWAI8HCE9ucb+wJPAO8AjEdKTa+wHzAfeAx6N
    kJ5cY1/gceB94LEI6ck19gEeAz4AHo+QnlxjH+BR4EPgiQjpyTX2Bh4BPgKeipCeXGMv4GHgY+Dp
    COnJNfYEHgI+AZ6NkJ5cY0/gQeBT4PkI6ck19gAeAD4DXoyQnlxjd+B+4HNgYYT05Bq7AfcBXwAv
    R0hPrrErcC+wFHglQnpyjV2Au4FlwGsR0pNr7AzcBSwHXo+QnlxjJ+BOYAXwRoT05Bo7Ar8BK4E3
    I6Qn19gB+BVYBTSE+h8P1P4Rv7sHKAAAAABJRU5ErkJggg==
    """
    
    # Cores
    GOLD = colors.Color(0.83, 0.69, 0.22)  # #d4af37
    DARK_BG = colors.Color(0.10, 0.10, 0.10)  # #1a1a1a
    DARK_CARD = colors.Color(0.16, 0.16, 0.16)  # #2a2a2a
    WHITE = colors.white
    GRAY = colors.Color(0.53, 0.53, 0.53)  # #888888
    GREEN = colors.Color(0.29, 0.85, 0.50)  # #4ade80
    RED = colors.Color(0.94, 0.27, 0.27)  # #f04444
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Configura estilos personalizados."""
        self.styles.add(ParagraphStyle(
            name='TitleGold',
            parent=self.styles['Title'],
            textColor=self.GOLD,
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=10,
        ))
        
        self.styles.add(ParagraphStyle(
            name='SubtitleGray',
            parent=self.styles['Normal'],
            textColor=self.GRAY,
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            textColor=self.GOLD,
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
        ))
        
        self.styles.add(ParagraphStyle(
            name='InfoLabel',
            parent=self.styles['Normal'],
            textColor=self.GRAY,
            fontSize=9,
        ))
        
        self.styles.add(ParagraphStyle(
            name='InfoValue',
            parent=self.styles['Normal'],
            textColor=colors.black,
            fontSize=10,
            fontName='Helvetica-Bold',
        ))
    
    def generate(
        self,
        user_name: str,
        user_email: str,
        user_cpf_cnpj: Optional[str],
        entries: List[dict],
        balance: Decimal,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> bytes:
        """
        Gera o PDF do extrato.
        
        Args:
            user_name: Nome do cliente
            user_email: Email do cliente
            user_cpf_cnpj: CPF/CNPJ do cliente
            entries: Lista de lançamentos
            balance: Saldo atual
            start_date: Data inicial do período
            end_date: Data final do período
        
        Returns:
            PDF em bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        elements = []
        
        # Header com logo
        elements.append(Paragraph("FLC Bank", self.styles['TitleGold']))
        elements.append(Paragraph("Extrato de Conta", self.styles['SubtitleGray']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Informações do cliente
        elements.append(Paragraph("Dados do Cliente", self.styles['SectionHeader']))
        
        client_data = [
            ['Nome:', user_name],
            ['Email:', user_email],
            ['CPF/CNPJ:', user_cpf_cnpj or 'Não informado'],
        ]
        
        client_table = Table(client_data, colWidths=[4*cm, 12*cm])
        client_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (0, -1), self.GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ]))
        elements.append(client_table)
        elements.append(Spacer(1, 0.5*cm))
        
        # Período e saldo
        period_text = "Todo o período"
        if start_date and end_date:
            period_text = f"{start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}"
        elif start_date:
            period_text = f"A partir de {start_date.strftime('%d/%m/%Y')}"
        elif end_date:
            period_text = f"Até {end_date.strftime('%d/%m/%Y')}"
        
        summary_data = [
            ['Período:', period_text, 'Saldo Atual:', f'R$ {balance:,.2f}'],
            ['Data de Emissão:', datetime.now().strftime('%d/%m/%Y %H:%M'), '', ''],
        ]
        
        summary_table = Table(summary_data, colWidths=[4*cm, 5*cm, 3.5*cm, 4.5*cm])
        summary_table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (0, -1), self.GRAY),
            ('TEXTCOLOR', (2, 0), (2, -1), self.GRAY),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
            ('TEXTCOLOR', (3, 0), (3, 0), colors.Color(0.15, 0.65, 0.35) if balance >= 0 else self.RED),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTSIZE', (3, 0), (3, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (2, 0), (3, 0), colors.Color(0.95, 0.95, 0.95)),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 1*cm))
        
        # Movimentações
        elements.append(Paragraph("Movimentações", self.styles['SectionHeader']))
        
        if entries:
            # Cabeçalho da tabela
            table_data = [['Data', 'Descrição', 'Tipo', 'Valor']]
            
            for entry in entries:
                entry_date = entry.get('created_at', '')
                if isinstance(entry_date, datetime):
                    entry_date = entry_date.strftime('%d/%m/%Y %H:%M')
                elif isinstance(entry_date, str):
                    try:
                        dt = datetime.fromisoformat(entry_date.replace('Z', '+00:00'))
                        entry_date = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                
                description = entry.get('description', '-')
                entry_type = entry.get('entry_type', '-')
                amount = entry.get('amount', 0)
                direction = entry.get('direction', 'CREDIT')
                
                # Formatar valor com sinal
                if direction == 'CREDIT':
                    value_str = f'+ R$ {float(amount):,.2f}'
                else:
                    value_str = f'- R$ {float(amount):,.2f}'
                
                table_data.append([entry_date, description, entry_type, value_str])
            
            entries_table = Table(table_data, colWidths=[3.5*cm, 8*cm, 2.5*cm, 3*cm])
            entries_table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), self.GOLD),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                
                # Corpo
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (0, -1), 'CENTER'),
                ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
                
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
                ('LINEBELOW', (0, 0), (-1, 0), 2, self.GOLD),
                
                # Zebra stripes
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            ]))
            
            # Colorir valores
            for i, entry in enumerate(entries, 1):
                direction = entry.get('direction', 'CREDIT')
                if direction == 'CREDIT':
                    entries_table.setStyle(TableStyle([
                        ('TEXTCOLOR', (3, i), (3, i), colors.Color(0.15, 0.65, 0.35)),
                    ]))
                else:
                    entries_table.setStyle(TableStyle([
                        ('TEXTCOLOR', (3, i), (3, i), self.RED),
                    ]))
            
            elements.append(entries_table)
        else:
            elements.append(Paragraph(
                "Nenhuma movimentação no período selecionado.",
                self.styles['Normal']
            ))
        
        elements.append(Spacer(1, 2*cm))
        
        # Rodapé
        footer_style = ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            textColor=self.GRAY,
            fontSize=8,
            alignment=TA_CENTER,
        )
        elements.append(Paragraph(
            "Este documento é um extrato informativo gerado automaticamente pelo FLC Bank.",
            footer_style
        ))
        elements.append(Paragraph(
            f"Emitido em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}",
            footer_style
        ))
        
        # Gerar PDF
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes


# Instância global
statement_pdf_generator = StatementPDFGenerator()
