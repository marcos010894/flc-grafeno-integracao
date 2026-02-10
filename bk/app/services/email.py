"""
FLC Bank - Serviço de Email
Envia notificações por email via SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço para envio de emails."""
    
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "Atendimento@flcbank.com.br")
        self.smtp_pass = os.getenv("SMTP_PASS", "yblmnjltpfaknlqd")
        self.email_from = os.getenv("EMAIL_FROM", "Atendimento@flcbank.com.br")
        
        # Emails para notificações administrativas
        self.admin_emails = [
            "ludtke260@gmail.com",
            "marcosmachadodev@gmail.com"
        ]
    
    def send_email(
        self,
        to: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[List[tuple]] = None,  # [(filename, content, mime_type)]
    ) -> bool:
        """
        Envia um email.
        
        Args:
            to: Lista de destinatários
            subject: Assunto do email
            body_html: Corpo do email em HTML
            body_text: Corpo do email em texto (opcional)
            attachments: Lista de anexos [(filename, content, mime_type)]
        
        Returns:
            True se enviado com sucesso
        """
        try:
            print(f"[EMAIL] Iniciando envio para: {to}")
            print(f"[EMAIL] Assunto: {subject}")
            print(f"[EMAIL] SMTP: {self.smtp_host}:{self.smtp_port}")
            print(f"[EMAIL] User: {self.smtp_user}")
            print(f"[EMAIL] Pass length: {len(self.smtp_pass)} chars, first 4: {self.smtp_pass[:4]}...")
            
            msg = MIMEMultipart('alternative')
            msg['From'] = f"FLC Bank <{self.email_from}>"
            msg['To'] = ", ".join(to)
            msg['Subject'] = subject
            
            # Adicionar corpo em texto
            if body_text:
                msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            
            # Adicionar corpo em HTML
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))
            
            # Adicionar anexos
            if attachments:
                for filename, content, mime_type in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(content)
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)
            
            # Conectar e enviar
            print(f"[EMAIL] Conectando ao SMTP...")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                print(f"[EMAIL] TLS OK, fazendo login...")
                server.login(self.smtp_user, self.smtp_pass)
                print(f"[EMAIL] Login OK, enviando...")
                server.sendmail(self.email_from, to, msg.as_string())
            
            print(f"[EMAIL] ✅ Email enviado com sucesso para {to}")
            logger.info(f"Email enviado para {to}: {subject}")
            return True
            
        except Exception as e:
            print(f"[EMAIL] ❌ ERRO ao enviar email: {str(e)}")
            logger.error(f"Erro ao enviar email: {str(e)}")
            return False
    
    def notify_pix_received(
        self,
        payer_name: str,
        amount: float,
        payer_cpf_cnpj: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Notifica sobre PIX recebido."""
        subject = f"💰 PIX Recebido - R$ {amount:,.2f}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #d4af37; margin: 0;">FLC Bank</h1>
                    <p style="color: #888;">Notificação de PIX Recebido</p>
                </div>
                
                <div style="background-color: #1a5a1a; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <h2 style="color: #4ade80; margin: 0 0 10px 0;">💰 PIX Recebido!</h2>
                    <p style="font-size: 28px; font-weight: bold; color: #4ade80; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Pagador:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">CPF/CNPJ:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_cpf_cnpj or 'Não informado'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Descrição:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{description or '-'}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Este é um email automático do FLC Bank. Não responda.
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email(self.admin_emails, subject, html)
    
    def notify_pix_send_request(
        self,
        user_name: str,
        user_email: str,
        amount: float,
        recipient_name: str,
        recipient_pix_key: str,
    ):
        """Notifica sobre solicitação de envio de PIX."""
        subject = f"📤 Solicitação de PIX - R$ {amount:,.2f} - {user_name}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #d4af37; margin: 0;">FLC Bank</h1>
                    <p style="color: #888;">Solicitação de Envio de PIX</p>
                </div>
                
                <div style="background-color: #5a3a1a; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <h2 style="color: #fbbf24; margin: 0 0 10px 0;">📤 Solicitação de PIX</h2>
                    <p style="font-size: 28px; font-weight: bold; color: #fbbf24; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <h3 style="color: #d4af37; margin: 20px 0 10px 0;">Solicitante:</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Nome:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{user_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Email:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{user_email}</td>
                    </tr>
                </table>
                
                <h3 style="color: #d4af37; margin: 20px 0 10px 0;">Destinatário:</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Nome:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Chave PIX:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_pix_key}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Este é um email automático do FLC Bank. Não responda.
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email(self.admin_emails, subject, html)

    def notify_user_pix_received(
        self,
        user_email: str,
        user_name: str,
        amount: float,
        payer_name: str,
        payer_document: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Notifica o usuário sobre PIX recebido na conta dele."""
        subject = f"💰 PIX Recebido - R$ {amount:,.2f}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #d4af37; margin: 0;">FLC Bank</h1>
                    <p style="color: #888;">Notificação de PIX</p>
                </div>
                
                <p style="color: #fff;">Olá, <strong>{user_name}</strong>!</p>
                
                <div style="background-color: #1a5a1a; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h2 style="color: #4ade80; margin: 0 0 10px 0;">💰 Você recebeu um PIX!</h2>
                    <p style="font-size: 32px; font-weight: bold; color: #4ade80; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">De:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Documento:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_document or 'Não informado'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Descrição:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{description or '-'}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Este é um email automático do FLC Bank. Não responda.
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email([user_email], subject, html)

    def notify_user_pix_sent(
        self,
        user_email: str,
        user_name: str,
        amount: float,
        recipient_name: str,
        recipient_pix_key: str,
        status: str = "enviado",
    ):
        """Notifica o usuário sobre PIX enviado."""
        status_info = {
            "enviado": ("✅", "#4ade80", "enviado com sucesso"),
            "pendente": ("⏳", "#fbbf24", "está pendente de aprovação"),
            "aprovado": ("✅", "#4ade80", "foi aprovado"),
            "rejeitado": ("❌", "#ef4444", "foi rejeitado"),
            "erro": ("❌", "#ef4444", "falhou"),
        }
        
        icon, color, msg = status_info.get(status, ("📤", "#d4af37", status))
        subject = f"{icon} PIX {status.capitalize()} - R$ {amount:,.2f}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #d4af37; margin: 0;">FLC Bank</h1>
                    <p style="color: #888;">Notificação de PIX</p>
                </div>
                
                <p style="color: #fff;">Olá, <strong>{user_name}</strong>!</p>
                
                <div style="background-color: #2a2a3a; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid {color};">
                    <h2 style="color: {color}; margin: 0 0 10px 0;">{icon} Seu PIX {msg}!</h2>
                    <p style="font-size: 28px; font-weight: bold; color: {color}; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Destinatário:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Chave PIX:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_pix_key}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Este é um email automático do FLC Bank. Não responda.
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email([user_email], subject, html)

    def notify_account_status(
        self,
        user_email: str,
        user_name: str,
        company_name: str,
        status: str,
        reason: Optional[str] = None,
    ):
        """Notifica o usuário sobre status da conta (aprovada/rejeitada)."""
        if status == "approved":
            subject = "✅ Sua conta foi aprovada! - FLC Bank"
            icon = "✅"
            title = "Conta Aprovada!"
            color = "#4ade80"
            message = "Parabéns! Sua conta foi aprovada e está pronta para uso."
            action_html = """
                <div style="text-align: center; margin: 20px 0;">
                    <a href="https://flcbank.com.br/portal" style="background-color: #d4af37; color: #000; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Acessar Portal
                    </a>
                </div>
            """
        elif status == "rejected":
            subject = "❌ Solicitação de conta não aprovada - FLC Bank"
            icon = "❌"
            title = "Conta Não Aprovada"
            color = "#ef4444"
            message = f"Infelizmente sua solicitação de conta não foi aprovada."
            if reason:
                message += f"<br><br><strong>Motivo:</strong> {reason}"
            action_html = """
                <p style="color: #888; text-align: center;">
                    Entre em contato conosco para mais informações.
                </p>
            """
        else:
            subject = f"📋 Atualização da sua conta - FLC Bank"
            icon = "📋"
            title = f"Status: {status}"
            color = "#fbbf24"
            message = f"O status da sua conta foi atualizado para: {status}"
            action_html = ""
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #d4af37; margin: 0;">FLC Bank</h1>
                    <p style="color: #888;">Notificação de Conta</p>
                </div>
                
                <p style="color: #fff;">Olá, <strong>{user_name}</strong>!</p>
                
                <div style="background-color: #2a2a3a; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid {color};">
                    <h2 style="color: {color}; margin: 0;">{icon} {title}</h2>
                </div>
                
                <p style="color: #fff; line-height: 1.6;">{message}</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Empresa:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{company_name}</td>
                    </tr>
                </table>
                
                {action_html}
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Este é um email automático do FLC Bank. Não responda.
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email([user_email], subject, html)
        # Também notifica os admins
        self.send_email(self.admin_emails, f"[ADMIN] {subject} - {company_name}", html)

    # =====================================================
    # NOTIFICAÇÕES DO PORTAL GRAFENO
    # =====================================================

    def notify_grafeno_pix_sent(
        self,
        user_email: str,
        user_name: str,
        amount: float,
        recipient_name: str,
        recipient_pix_key: str,
        status: str = "enviado",
        transaction_id: Optional[str] = None,
    ):
        """Notifica sobre PIX enviado pelo portal Grafeno."""
        status_info = {
            "enviado": ("✅", "#4ade80", "enviado com sucesso"),
            "pendente": ("⏳", "#fbbf24", "está sendo processado"),
            "processando": ("⏳", "#fbbf24", "está sendo processado"),
            "aprovado": ("✅", "#4ade80", "foi concluído com sucesso"),
            "concluido": ("✅", "#4ade80", "foi concluído com sucesso"),
            "rejeitado": ("❌", "#ef4444", "foi rejeitado"),
            "erro": ("❌", "#ef4444", "falhou"),
            "falhou": ("❌", "#ef4444", "falhou"),
        }
        
        icon, color, msg = status_info.get(status.lower(), ("📤", "#d4af37", status))
        subject = f"{icon} PIX {msg} - R$ {amount:,.2f}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #10b981; margin: 0;">Portal Grafeno</h1>
                    <p style="color: #888;">Notificação de PIX Enviado</p>
                </div>
                
                <p style="color: #fff;">Olá, <strong>{user_name}</strong>!</p>
                
                <div style="background-color: #1a3a2a; border-radius: 8px; padding: 20px; margin: 20px 0; border-left: 4px solid {color};">
                    <h2 style="color: {color}; margin: 0 0 10px 0;">{icon} Seu PIX {msg}!</h2>
                    <p style="font-size: 32px; font-weight: bold; color: {color}; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Destinatário:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Chave PIX:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{recipient_pix_key}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">ID Transação:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right; font-family: monospace; font-size: 12px;">{transaction_id or '-'}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Portal Grafeno - FLC Bank
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email([user_email], subject, html)

    def notify_grafeno_pix_received(
        self,
        user_email: str,
        user_name: str,
        amount: float,
        payer_name: str,
        payer_document: Optional[str] = None,
        description: Optional[str] = None,
        end_to_end_id: Optional[str] = None,
    ):
        """Notifica sobre PIX recebido na conta Grafeno."""
        subject = f"💰 PIX Recebido - R$ {amount:,.2f}"
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #1a1a1a; color: #ffffff; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #2a2a2a; border-radius: 10px; padding: 30px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #10b981; margin: 0;">Portal Grafeno</h1>
                    <p style="color: #888;">Notificação de PIX Recebido</p>
                </div>
                
                <p style="color: #fff;">Olá, <strong>{user_name}</strong>!</p>
                
                <div style="background-color: #1a5a1a; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <h2 style="color: #4ade80; margin: 0 0 10px 0;">💰 Você recebeu um PIX!</h2>
                    <p style="font-size: 32px; font-weight: bold; color: #4ade80; margin: 0;">
                        R$ {amount:,.2f}
                    </p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Pagador:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">CPF/CNPJ:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{payer_document or 'Não informado'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">Descrição:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right;">{description or '-'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #888;">End-to-End ID:</td>
                        <td style="padding: 10px 0; border-bottom: 1px solid #444; color: #fff; text-align: right; font-family: monospace; font-size: 10px;">{end_to_end_id or '-'}</td>
                    </tr>
                </table>
                
                <p style="color: #888; font-size: 12px; text-align: center; margin-top: 30px;">
                    Portal Grafeno - FLC Bank
                </p>
            </div>
        </body>
        </html>
        """
        
        self.send_email([user_email], subject, html)


# Instância global
email_service = EmailService()
