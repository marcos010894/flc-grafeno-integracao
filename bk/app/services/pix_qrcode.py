"""
FLC Bank - Gerador de QR Code PIX
Baseado no padrão BR Code do Banco Central
"""

import re
import crcmod
from decimal import Decimal
from typing import Optional
import base64
import io

# Configuração da conta FLC Bank (Grafeno)
PIX_KEY_EMAIL = "fabio@flcbank.com.br"
PIX_KEY_CNPJ = "38024144000150"
MERCHANT_NAME = "FLC BANK"
MERCHANT_CITY = "SAO PAULO"
BANK_CODE = "274"
AGENCY = "0001"
ACCOUNT = "08185935-7"


def _calculate_crc16(payload: str) -> str:
    """Calcula o CRC16 CCITT-FALSE do payload."""
    crc16_func = crcmod.mkCrcFun(0x11021, initCrc=0xFFFF, xorOut=0x0000)
    crc = crc16_func(payload.encode('utf-8'))
    return format(crc, '04X')


def _format_emv_field(id: str, value: str) -> str:
    """Formata um campo no padrão EMV (ID + Length + Value)."""
    length = str(len(value)).zfill(2)
    return f"{id}{length}{value}"


def generate_pix_payload(
    amount: Optional[Decimal] = None,
    transaction_id: Optional[str] = None,
    description: Optional[str] = None,
) -> str:
    """
    Gera o payload do PIX no formato BR Code padrão.
    Formato simplificado conforme manual do BACEN.
    """
    # Payload Format Indicator (ID 00) - Sempre "01"
    payload = _format_emv_field("00", "01")
    
    # Merchant Account Information - PIX (ID 26)
    # 00 = GUI obrigatório: br.gov.bcb.pix
    # 01 = Chave PIX
    gui = _format_emv_field("00", "br.gov.bcb.pix")
    pix_key = _format_emv_field("01", PIX_KEY_EMAIL)
    merchant_info = gui + pix_key
    payload += _format_emv_field("26", merchant_info)
    
    # Merchant Category Code (ID 52) - "0000" = não informado
    payload += _format_emv_field("52", "0000")
    
    # Transaction Currency (ID 53) - "986" = BRL
    payload += _format_emv_field("53", "986")
    
    # Transaction Amount (ID 54) - valor
    if amount:
        amount_str = f"{float(amount):.2f}"
        payload += _format_emv_field("54", amount_str)
    
    # Country Code (ID 58) - "BR"
    payload += _format_emv_field("58", "BR")
    
    # Merchant Name (ID 59) - Nome do recebedor
    payload += _format_emv_field("59", MERCHANT_NAME)
    
    # Merchant City (ID 60) - Cidade
    payload += _format_emv_field("60", MERCHANT_CITY)
    
    # CRC16 (ID 63) - Checksum
    payload += "6304"
    crc = _calculate_crc16(payload)
    payload = payload[:-4] + f"6304{crc}"
    
    return payload


def generate_pix_qrcode_base64(
    amount: Optional[Decimal] = None,
    transaction_id: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Gera o QR Code PIX em formato base64.
    
    Returns:
        Dict com payload (copia e cola) e qrcode_base64 (imagem)
    """
    try:
        import qrcode
        from qrcode.image.pure import PyPNGImage
    except ImportError:
        # Se qrcode não estiver instalado, retorna só o payload
        payload = generate_pix_payload(amount, transaction_id, description)
        return {
            "payload": payload,
            "qrcode_base64": None,
            "message": "QR Code image not available (qrcode library not installed)"
        }
    
    payload = generate_pix_payload(amount, transaction_id, description)
    
    # Gerar QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    # Criar imagem
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Converter para base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return {
        "payload": payload,
        "qrcode_base64": f"data:image/png;base64,{img_base64}",
        "pix_key": PIX_KEY_EMAIL,
        "merchant_name": MERCHANT_NAME,
        "bank_info": {
            "bank_code": BANK_CODE,
            "bank_name": "Grafeno",
            "agency": AGENCY,
            "account": ACCOUNT,
        }
    }


def get_deposit_info() -> dict:
    """Retorna informações para depósito via PIX."""
    return {
        "pix_key": PIX_KEY_EMAIL,
        "pix_key_type": "email",
        "merchant_name": MERCHANT_NAME,
        "bank": {
            "code": BANK_CODE,
            "name": "Grafeno",
            "agency": AGENCY,
            "account": ACCOUNT,
        },
        "instructions": [
            "1. Copie a chave PIX (Email) ou escaneie o QR Code",
            "2. Faça o PIX do valor desejado",
            "3. Aguarde a confirmação (geralmente em segundos)",
            "4. O valor será creditado automaticamente na sua conta",
        ]
    }
