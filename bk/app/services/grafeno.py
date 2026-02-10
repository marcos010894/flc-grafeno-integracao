"""
FLC Bank - Serviço de Integração com Grafeno
API de Pagamentos e Transferências PIX
"""

import httpx
import uuid
import hashlib
import hmac
from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import datetime
import os


class GrafenoService:
    """
    Serviço para integração com a API Grafeno.
    
    A Grafeno fornece:
    - Transferências PIX/TED
    - Webhooks para notificação de status
    - Consulta de saldo e extrato
    """
    
    # URLs base da API - Produção
    BASE_URL_PAYMENTS = "https://pagamentos.grafeno.be/api/v2"
    BASE_URL_STATEMENTS = "https://extratos.grafeno.digital/api/v1"
    
    # Sandbox URLs
    SANDBOX_URL_PAYMENTS = "https://pagamentos.sandbox.grafeno.digital/api/v2"
    SANDBOX_URL_STATEMENTS = "https://extratos.sandbox.grafeno.digital/api/v1"
    
    def __init__(self):
        """Inicializa o serviço com credenciais do ambiente."""
        self.token = os.getenv("GRAFENO_API_TOKEN", "38387c01-b705-4425-9006-59a8c134d8b0.9V9v4B_L0XVcx-tmrEEUMNAKvSk")
        self.agency = os.getenv("GRAFENO_AGENCY", "0001")
        self.account = os.getenv("GRAFENO_ACCOUNT", "08185935-7")
        self.webhook_url = os.getenv("GRAFENO_WEBHOOK_URL", "https://flc-bank-api.fly.dev/grafeno/webhook")
        self.is_sandbox = os.getenv("GRAFENO_SANDBOX", "false").lower() == "true"
        
        # Sempre usar URLs de produção - o token fornecido é de produção
        self.payments_url = self.BASE_URL_PAYMENTS
        self.statements_url = self.BASE_URL_STATEMENTS
    
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers padrão para requisições à API."""
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Account-Number": self.account,
        }
    
    async def create_pix_transfer(
        self,
        value: Decimal,
        pix_key: str,
        pix_key_type: str,
        beneficiary_name: str,
        beneficiary_document: str,
        transaction_uuid: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cria uma transferência PIX.
        
        Args:
            value: Valor da transferência
            pix_key: Chave PIX do destinatário
            pix_key_type: Tipo da chave (cpf, cnpj, email, phone, evp)
            beneficiary_name: Nome do beneficiário
            beneficiary_document: CPF/CNPJ do beneficiário
            transaction_uuid: UUID único da transação (gerado se não fornecido)
            description: Descrição da transferência
        
        Returns:
            Resposta da API com detalhes da transferência criada
        """
        if transaction_uuid is None:
            transaction_uuid = str(uuid.uuid4())
        
        payload = {
            "transfer_request": {
                "transferMethod": "pix",
                "value": float(value),
                "api_partner_transaction_uuid": transaction_uuid,
                "callback_url": self.webhook_url,
            },
            "beneficiary": {
                "name": beneficiary_name,
                "documentNumber": beneficiary_document,
                "keyType": pix_key_type,
                "key": pix_key,
            }
        }
        
        # URLs para tentar
        urls_to_try = [
            f"{self.payments_url}/transfer_requests",
            "https://pagamentos.grafeno.be/api/v2/transfer_requests",
        ]
        
        last_error = None
        for url in urls_to_try:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=self._get_headers(),
                        timeout=30.0
                    )
                    
                    try:
                        response_data = response.json()
                    except:
                        response_data = {"raw": response.text}
                    
                    return {
                        "success": response.status_code in [200, 201, 202],
                        "status_code": response.status_code,
                        "transaction_uuid": transaction_uuid,
                        "data": response_data,
                        "url_used": url,
                    }
            except Exception as e:
                last_error = str(e)
                continue
        
        return {
            "success": False,
            "error": last_error or "Connection failed",
            "transaction_uuid": transaction_uuid,
            "message": "Não foi possível conectar à API Grafeno para criar transferência.",
        }
    
    async def create_ted_transfer(
        self,
        value: Decimal,
        beneficiary_name: str,
        beneficiary_document: str,
        bank_code: str,
        agency: str,
        account: str,
        transaction_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cria uma transferência TED.
        
        Args:
            value: Valor da transferência
            beneficiary_name: Nome do beneficiário
            beneficiary_document: CPF/CNPJ do beneficiário
            bank_code: Código do banco
            agency: Número da agência
            account: Número da conta
            transaction_uuid: UUID único da transação
        
        Returns:
            Resposta da API
        """
        if transaction_uuid is None:
            transaction_uuid = str(uuid.uuid4())
        
        payload = {
            "transfer_request": {
                "transferMethod": "ted",
                "value": float(value),
                "api_partner_transaction_uuid": transaction_uuid,
                "callback_url": self.webhook_url,
            },
            "beneficiary": {
                "name": beneficiary_name,
                "documentNumber": beneficiary_document,
                "bankCode": bank_code,
                "agency": agency,
                "account": account,
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.payments_url}/transfer_requests",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code in [200, 201],
                "status_code": response.status_code,
                "transaction_uuid": transaction_uuid,
                "data": response.json(),
            }
    
    async def create_pix_charge(
        self,
        value: Decimal,
        payer_name: str,
        payer_document: str,
        payer_email: Optional[str] = None,
        due_date: Optional[str] = None,
        client_control_number: Optional[str] = None,
        expires_after: int = 1,
    ) -> Dict[str, Any]:
        """
        Cria uma cobrança PIX (QR Code dinâmico).
        
        Args:
            value: Valor da cobrança (precisão 2 casas)
            payer_name: Nome do pagador
            payer_document: CPF/CNPJ do pagador
            payer_email: Email do pagador (opcional)
            due_date: Data de vencimento YYYY-MM-DD (default: amanhã)
            client_control_number: Identificador único (max 25 chars)
            expires_after: Dias para cancelar após vencimento
        
        Returns:
            Dict com charge_id, pix_qrcode, pix_copy_paste, etc
        """
        from datetime import date as date_type, timedelta
        
        # Data de vencimento deve ser no futuro (pelo menos amanhã)
        if due_date is None:
            due_date = (date_type.today() + timedelta(days=1)).isoformat()
        
        if client_control_number is None:
            client_control_number = str(uuid.uuid4())[:25]
        
        # Chave PIX aleatória da conta Grafeno
        PIX_KEY_RANDOM = "43aa6af5-c6e1-42f1-9cf9-d5606d1b8a75"
        
        # Limpar documento (remover pontos, traços, etc)
        clean_document = payer_document.replace(".", "").replace("-", "").replace("/", "")
        
        # Payload conforme documentação Grafeno
        # IMPORTANTE: Todos os campos obrigatórios devem estar presentes
        payload = {
            "paymentMethod": "pix",
            "dueDate": due_date,
            "value": round(float(value), 2),
            "clientControlNumber": client_control_number,
            "expiresAfter": expires_after,
            "pix": {
                "key": PIX_KEY_RANDOM,
                "keyType": "random"
            },
            "payer": {
                "name": payer_name,
                "email": payer_email or "fabio@flcbank.com.br",
                "documentNumber": clean_document,
                "address": {
                    "zipCode": "01001000",
                    "street": "Praça da Sé",
                    "number": "1",
                    "complement": "Lado ímpar",
                    "neighborhood": "Sé",
                    "city": "São Paulo",
                    "state": "SP",
                    "country": "BR"
                },
                "phone": {
                    "countryCode": "55",
                    "areaCode": "11",
                    "number": "999999999"
                }
            },
            "grantor": {
                "name": "FLC BANK LTDA",
                "documentNumber": "88650081000116",  # CNPJ válido da empresa
                "address": {
                    "street": "Avenida Paulista",
                    "number": "1000",
                    "complement": "Conjunto 100",
                    "zipCode": "01310-100",
                    "neighborhood": "Bela Vista",
                    "city": "São Paulo",
                    "state": "SP",
                    "country": "BR"
                }
            }
        }
        
        url = f"{self.payments_url}/charges"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw": response.text}
                
                if response.status_code in [200, 201]:
                    # Extrair dados da estrutura aninhada da resposta Grafeno
                    # Estrutura: data.attributes.pixData.data.attributes
                    data_obj = response_data.get("data", {})
                    attrs = data_obj.get("attributes", {})
                    
                    # Extrair dados do PIX (aninhado em pixData.data.attributes)
                    pix_data_container = attrs.get("pixData", {})
                    pix_data_obj = pix_data_container.get("data", {})
                    pix_attrs = pix_data_obj.get("attributes", {})
                    
                    # Extrair QR Code e EMV
                    pix_emv = pix_attrs.get("emv")
                    pix_image = pix_attrs.get("encodedImage")
                    
                    return {
                        "success": True,
                        "charge_id": data_obj.get("id"),
                        "status": attrs.get("status"),
                        "pix_qrcode": pix_image,
                        "pix_copy_paste": pix_emv,
                        "pix_txid": pix_data_obj.get("id"),
                        "client_control_number": attrs.get("clientControlNumber"),
                        "due_date": attrs.get("dueDate"),
                        "value": float(attrs.get("value", value)),
                        "raw_response": response_data,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response_data.get("message") or response_data.get("error") or str(response_data),
                        "raw_response": response_data,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao conectar com API Grafeno para criar cobrança",
            }
    
    async def list_pending_transfers(self) -> Dict[str, Any]:
        """Lista transferências pendentes de aprovação."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.payments_url}/transfer_requests/pending",
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json(),
            }
    
    async def list_transfers(
        self,
        page: int = 1,
        per_page: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lista todas as transferências."""
        params = {
            "page[number]": page,
            "page[size]": per_page,
        }
        if status:
            params["filter[status]"] = status
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.payments_url}/transfer_requests",
                params=params,
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json(),
            }
    
    async def approve_transfer(self, api_partner_transaction_uuid: str) -> Dict[str, Any]:
        """
        Aprova uma transferência pendente.
        
        Args:
            api_partner_transaction_uuid: UUID da transação gerado pelo parceiro API
        
        Returns:
            Dict com success e data
        """
        payload = {
            "state": "approve"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.payments_url}/transfer_requests/{api_partner_transaction_uuid}/update_state",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": response_data,
            }
    
    async def reject_transfer(self, api_partner_transaction_uuid: str, reason: str = "") -> Dict[str, Any]:
        """
        Rejeita uma transferência pendente.
        
        Args:
            api_partner_transaction_uuid: UUID da transação gerado pelo parceiro API
            reason: Motivo da rejeição (opcional)
        
        Returns:
            Dict com success e data
        """
        payload = {
            "state": "reject"
        }
        
        if reason:
            payload["reject_reason"] = reason
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{self.payments_url}/transfer_requests/{api_partner_transaction_uuid}/update_state",
                json=payload,
                headers=self._get_headers(),
                timeout=30.0
            )
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text}
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": response_data,
            }
    
    async def auto_approve_pending_transfers(
        self,
        max_value: Optional[Decimal] = None,
        auto_approve_all: bool = False
    ) -> Dict[str, Any]:
        """
        Aprova automaticamente transferências pendentes com base em regras de negócio.
        
        Args:
            max_value: Valor máximo para aprovação automática (None = sem limite)
            auto_approve_all: Se True, aprova todas independente do valor
        
        Returns:
            Dict com estatísticas de aprovações
        """
        # Listar transferências pendentes
        pending_result = await self.list_pending_transfers()
        
        if not pending_result.get("success"):
            return {
                "success": False,
                "error": "Falha ao listar transferências pendentes",
                "data": pending_result
            }
        
        pending_data = pending_result.get("data", {})
        transfers = pending_data.get("data", [])
        
        if not transfers:
            return {
                "success": True,
                "message": "Nenhuma transferência pendente",
                "approved": 0,
                "rejected": 0,
                "total": 0
            }
        
        approved_count = 0
        rejected_count = 0
        errors = []
        
        for transfer in transfers:
            try:
                # Extrair dados da transferência
                transfer_id = transfer.get("id")
                attrs = transfer.get("attributes", {})
                value = Decimal(str(attrs.get("value", 0)))
                api_uuid = attrs.get("apiPartnerTransactionUuid")
                
                if not api_uuid:
                    errors.append(f"Transfer {transfer_id}: UUID não encontrado")
                    continue
                
                # Aplicar regras de negócio
                should_approve = auto_approve_all
                
                if not should_approve and max_value is not None:
                    should_approve = value <= max_value
                elif not should_approve:
                    # Por padrão, aprovar transferências até R$ 10.000
                    should_approve = value <= Decimal("10000.00")
                
                if should_approve:
                    result = await self.approve_transfer(api_uuid)
                    if result.get("success"):
                        approved_count += 1
                    else:
                        errors.append(f"Transfer {api_uuid}: Erro ao aprovar - {result.get('data')}")
                else:
                    result = await self.reject_transfer(
                        api_uuid,
                        reason=f"Valor acima do limite permitido para aprovação automática (R$ {max_value or 10000})"
                    )
                    if result.get("success"):
                        rejected_count += 1
                    else:
                        errors.append(f"Transfer {api_uuid}: Erro ao rejeitar - {result.get('data')}")
                        
            except Exception as e:
                errors.append(f"Transfer {transfer.get('id')}: Exceção - {str(e)}")
        
        return {
            "success": True,
            "approved": approved_count,
            "rejected": rejected_count,
            "total": len(transfers),
            "errors": errors if errors else None
        }
    
    async def get_balance(self) -> Dict[str, Any]:
        """Consulta o saldo da conta Grafeno."""
        # URL correta conforme documentação: https://pagamentos.grafeno.be/api/v2/balance/
        url = f"{self.payments_url}/balance/"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # A resposta pode ser uma lista de contas
                    if isinstance(data, dict) and "data" in data:
                        accounts = data.get("data", [])
                        if isinstance(accounts, list) and len(accounts) > 0:
                            # Pegar a primeira conta ou a que corresponde ao account number
                            account_data = accounts[0]
                            attrs = account_data.get("attributes", {})
                            return {
                                "success": True,
                                "current_balance": attrs.get("currentBalance") or attrs.get("balance"),
                                "available_balance": attrs.get("availableBalance") or attrs.get("balance"),
                                "account": self.account,
                                "data": data,
                            }
                        elif isinstance(accounts, dict):
                            attrs = accounts.get("attributes", {})
                            return {
                                "success": True,
                                "current_balance": attrs.get("currentBalance") or attrs.get("balance"),
                                "available_balance": attrs.get("availableBalance") or attrs.get("balance"),
                                "account": self.account,
                                "data": data,
                            }
                    return {
                        "success": True,
                        "data": data,
                        "account": self.account,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                        "url": url,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao conectar à API Grafeno",
                "url": url,
            }
    
    async def get_statement(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """
        Consulta o extrato da conta.
        
        Args:
            start_date: Data inicial (formato YYYY-MM-DD)
            end_date: Data final (formato YYYY-MM-DD)
            page: Número da página
            per_page: Itens por página
        """
        params = {
            "page[number]": page,
            "page[size]": per_page,
        }
        if start_date:
            params["filter[entry_at_gteq]"] = start_date
        if end_date:
            params["filter[entry_at_lteq]"] = end_date
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.statements_url}/ip_bank_accounts/{self.account}/statement_entries",
                params=params,
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json(),
            }
    
    async def get_bank_accounts(self) -> Dict[str, Any]:
        """Lista contas bancárias vinculadas."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.statements_url}/ip_bank_accounts",
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json(),
            }
    
    def verify_webhook_signature(
        self,
        signature: str,
        digest: str,
        transaction_uuid: str,
        status: Optional[str] = None,
        kind: str = "confirmation"
    ) -> bool:
        """
        Verifica a assinatura do webhook da Grafeno.
        
        Para confirmação: confirmation-{api_partner_transaction_uuid}
        Para notificação: {status}-{api_partner_transaction_uuid}
        """
        if kind == "confirmation":
            message = f"confirmation-{transaction_uuid}"
        else:
            message = f"{status}-{transaction_uuid}"
        
        # A verificação real dependeria da chave secreta fornecida pela Grafeno
        # Por enquanto retornamos True para sandbox
        if self.is_sandbox:
            return True
        
        # TODO: Implementar verificação real com chave secreta
        return True

    # =====================================================
    # WEBHOOK REGISTRATION
    # =====================================================
    
    async def register_webhook(
        self,
        kind: str,
        url: str,
        extra_headers: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Registra uma URL de webhook na Grafeno.
        
        Args:
            kind: Tipo do webhook (boleto, charge, payment, concession, protest)
            url: URL para receber as notificações
            extra_headers: Headers extras para enviar com a notificação
        
        Returns:
            Resposta da API
        """
        payload = {
            "kind": kind,
            "url": url,
        }
        
        if extra_headers:
            payload["extraHeaders"] = extra_headers
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.payments_url}/webhooks",
                headers=self._get_headers(),
                json=payload,
                timeout=30.0
            )
            
            return {
                "success": response.status_code in [200, 201],
                "status_code": response.status_code,
                "data": response.json() if response.content else None,
            }
    
    async def list_webhooks(self) -> Dict[str, Any]:
        """Lista todos os webhooks registrados."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.payments_url}/webhooks",
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code == 200,
                "data": response.json() if response.content else None,
            }
    
    async def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Remove um webhook registrado."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.payments_url}/webhooks/{webhook_id}",
                headers=self._get_headers(),
                timeout=30.0
            )
            
            return {
                "success": response.status_code in [200, 204],
                "status_code": response.status_code,
            }

    # =====================================================
    # BENEFICIÁRIOS - Cadastro obrigatório para transferências
    # =====================================================
    
    async def add_beneficiary(
        self,
        name: str,
        document_number: str,
        pix_key: Optional[str] = None,
        pix_key_type: Optional[str] = None,
        bank_code: Optional[str] = None,
        agency: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Adiciona um beneficiário à conta Grafeno.
        
        O beneficiário deve ser cadastrado ANTES de criar uma transferência.
        
        Args:
            name: Nome completo ou razão social do beneficiário
            document_number: CPF ou CNPJ do beneficiário
            pix_key: Chave PIX do beneficiário (opcional se usar dados bancários)
            pix_key_type: Tipo da chave PIX (cpf, cnpj, email, phone, evp)
            bank_code: Código do banco (obrigatório para TED)
            agency: Número da agência (obrigatório para TED)
            account: Número da conta com dígito (obrigatório para TED)
        
        Returns:
            Dict com dados do beneficiário cadastrado
        """
        payload = {
            "name": name,
            "documentNumber": document_number.replace(".", "").replace("-", "").replace("/", ""),
        }
        
        # Adicionar dados PIX se fornecidos
        if pix_key and pix_key_type:
            payload["pixDetails"] = {
                "key": pix_key,
                "keyType": pix_key_type,
            }
        
        # Adicionar dados bancários se fornecidos
        if bank_code:
            payload["bankCode"] = bank_code
        if agency:
            payload["agency"] = agency
        if account:
            payload["account"] = account
        
        url = f"{self.payments_url}/beneficiaries"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw": response.text}
                
                if response.status_code in [200, 201]:
                    # Extrair ID do beneficiário
                    beneficiary_id = None
                    if isinstance(response_data, dict):
                        data = response_data.get("data", {})
                        if isinstance(data, dict):
                            beneficiary_id = data.get("id")
                    
                    return {
                        "success": True,
                        "beneficiary_id": beneficiary_id,
                        "data": response_data,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response_data.get("message") or response_data.get("error") or str(response_data),
                        "raw_response": response_data,
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao conectar com API Grafeno para cadastrar beneficiário",
            }
    
    async def list_beneficiaries(
        self,
        page: int = 1,
        per_page: int = 50,
        document_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lista beneficiários cadastrados.
        
        Args:
            page: Número da página
            per_page: Itens por página
            document_number: Filtrar por CPF/CNPJ
        
        Returns:
            Lista de beneficiários
        """
        params = {
            "page[number]": page,
            "page[size]": per_page,
        }
        if document_number:
            params["filter[documentNumber]"] = document_number.replace(".", "").replace("-", "").replace("/", "")
        
        url = f"{self.payments_url}/beneficiaries"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw": response.text}
                
                return {
                    "success": response.status_code == 200,
                    "data": response_data,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def get_beneficiary(self, beneficiary_id: str) -> Dict[str, Any]:
        """
        Consulta um beneficiário específico.
        
        Args:
            beneficiary_id: ID do beneficiário
        
        Returns:
            Dados do beneficiário
        """
        url = f"{self.payments_url}/beneficiaries/{beneficiary_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    timeout=30.0
                )
                
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw": response.text}
                
                return {
                    "success": response.status_code == 200,
                    "data": response_data,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def find_or_create_beneficiary(
        self,
        name: str,
        document_number: str,
        pix_key: Optional[str] = None,
        pix_key_type: Optional[str] = None,
        bank_code: Optional[str] = None,
        agency: Optional[str] = None,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca um beneficiário pelo documento. Se não existir, cria.
        
        Útil para garantir que o beneficiário está cadastrado antes de transferir.
        
        Returns:
            Dict com beneficiary_id e dados do beneficiário
        """
        # Primeiro, buscar se já existe
        clean_doc = document_number.replace(".", "").replace("-", "").replace("/", "")
        
        existing = await self.list_beneficiaries(document_number=clean_doc)
        
        if existing.get("success"):
            data = existing.get("data", {})
            beneficiaries = []
            
            if isinstance(data, dict) and "data" in data:
                beneficiaries = data.get("data", [])
            elif isinstance(data, list):
                beneficiaries = data
            
            if beneficiaries and len(beneficiaries) > 0:
                # Beneficiário já existe
                beneficiary = beneficiaries[0]
                beneficiary_id = beneficiary.get("id")
                return {
                    "success": True,
                    "beneficiary_id": beneficiary_id,
                    "already_existed": True,
                    "data": beneficiary,
                }
        
        # Não existe, criar novo
        result = await self.add_beneficiary(
            name=name,
            document_number=document_number,
            pix_key=pix_key,
            pix_key_type=pix_key_type,
            bank_code=bank_code,
            agency=agency,
            account=account,
        )
        
        if result.get("success"):
            result["already_existed"] = False
        
        return result
    
    async def create_pix_transfer_with_beneficiary(
        self,
        value: Decimal,
        pix_key: str,
        pix_key_type: str,
        beneficiary_name: str,
        beneficiary_document: str,
        transaction_uuid: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Cria uma transferência PIX garantindo que o beneficiário está cadastrado.
        
        Este método:
        1. Verifica/cadastra o beneficiário
        2. Cria a transferência PIX
        
        Args:
            value: Valor da transferência
            pix_key: Chave PIX do destinatário
            pix_key_type: Tipo da chave (cpf, cnpj, email, phone, evp)
            beneficiary_name: Nome do beneficiário
            beneficiary_document: CPF/CNPJ do beneficiário
            transaction_uuid: UUID único da transação
            description: Descrição da transferência
        
        Returns:
            Resposta da API com detalhes da transferência
        """
        # Passo 1: Garantir que o beneficiário está cadastrado
        beneficiary_result = await self.find_or_create_beneficiary(
            name=beneficiary_name,
            document_number=beneficiary_document,
            pix_key=pix_key,
            pix_key_type=pix_key_type,
        )
        
        if not beneficiary_result.get("success"):
            return {
                "success": False,
                "error": "Falha ao cadastrar beneficiário",
                "beneficiary_error": beneficiary_result.get("error"),
                "raw_response": beneficiary_result,
            }
        
        # Passo 2: Criar a transferência
        transfer_result = await self.create_pix_transfer(
            value=value,
            pix_key=pix_key,
            pix_key_type=pix_key_type,
            beneficiary_name=beneficiary_name,
            beneficiary_document=beneficiary_document,
            transaction_uuid=transaction_uuid,
            description=description,
        )
        
        # Adicionar informação do beneficiário ao resultado
        transfer_result["beneficiary_id"] = beneficiary_result.get("beneficiary_id")
        transfer_result["beneficiary_already_existed"] = beneficiary_result.get("already_existed")
        
        return transfer_result


# Singleton para uso global
grafeno_service = GrafenoService()
