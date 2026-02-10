"""
Script para monitorar e aprovar transferências pendentes em tempo real
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.grafeno import GrafenoService
from decimal import Decimal
import json

async def monitor_and_approve():
    grafeno = GrafenoService()
    
    print("=" * 80)
    print("MONITORAMENTO: Transferencias Pendentes")
    print("=" * 80)
    print("\nAguardando nova transferencia...")
    print("(Pressione Ctrl+C para parar)\n")
    
    last_count = 0
    
    while True:
        try:
            # Listar transferências pendentes
            pending = await grafeno.list_pending_transfers()
            
            if not pending.get('success'):
                print(f"Erro ao listar: {pending}")
                await asyncio.sleep(5)
                continue
            
            data = pending.get('data', {})
            transfers = data.get('data', [])
            current_count = len(transfers)
            
            # Se houver nova transferência
            if current_count > last_count:
                print(f"\n{'='*80}")
                print(f"NOVA TRANSFERENCIA DETECTADA! Total: {current_count}")
                print(f"{'='*80}\n")
                
                # Processar cada transferência
                for transfer in transfers:
                    transfer_id = transfer.get('id')
                    attrs = transfer.get('attributes', {})
                    value = attrs.get('value', 0)
                    status = attrs.get('status', 'unknown')
                    api_uuid = attrs.get('apiPartnerTransactionUuid')
                    beneficiary = attrs.get('beneficiary', {}).get('data', {}).get('attributes', {})
                    
                    print(f"Transferencia ID: {transfer_id}")
                    print(f"UUID: {api_uuid}")
                    print(f"Valor: R$ {value}")
                    print(f"Status: {status}")
                    print(f"Beneficiario: {beneficiary.get('name', 'N/A')}")
                    print(f"\nDados completos:")
                    print(json.dumps(transfer, indent=2, ensure_ascii=False))
                    
                    # Tentar aprovar
                    if api_uuid:
                        print(f"\nTentando aprovar UUID: {api_uuid}...")
                        result = await grafeno.approve_transfer(api_uuid)
                        
                        print(f"\nResultado da aprovacao:")
                        print(f"Success: {result.get('success')}")
                        print(f"Status Code: {result.get('status_code')}")
                        print(f"Data: {json.dumps(result.get('data'), indent=2, ensure_ascii=False)}")
                        
                        if result.get('success'):
                            print(f"\n*** APROVADA COM SUCESSO! ***")
                        else:
                            print(f"\n*** ERRO AO APROVAR ***")
                    else:
                        print(f"\nUUID nao encontrado!")
                    
                    print(f"\n{'='*80}\n")
                
                last_count = current_count
            elif current_count < last_count:
                print(f"\nTransferencia removida. Total agora: {current_count}")
                last_count = current_count
            
            # Aguardar 3 segundos antes de verificar novamente
            await asyncio.sleep(3)
            
        except KeyboardInterrupt:
            print("\n\nMonitoramento interrompido pelo usuario.")
            break
        except Exception as e:
            print(f"\nErro: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(monitor_and_approve())
