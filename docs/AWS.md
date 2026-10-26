# Implantação do relay na AWS

O autor relata ter criado e configurado uma instância AWS para o projeto. Estas são instruções para recriar o ambiente; a instância original não foi acessada nem validada nesta revisão.

## Ambiente de demonstração

1. Prepare uma instância EC2 Linux com Python 3 e acesso administrativo próprio.
2. Envie a pasta `aws_relay` à instância, sem chaves privadas no repositório.
3. Restrinja SSH no Security Group ao IP administrativo e prefira acesso privado via VPN para os testes do relay.
4. Permita TCP 5938 somente das origens necessárias ao laboratório. Não abra indiscriminadamente a porta para a internet: o aplicativo não tem TLS.
5. Na instância, execute:

```bash
cd aws_relay
python3 server.py
```

O servidor escuta em `0.0.0.0:5938`. O processo acima fica ligado ao terminal; serviço com reinício automático e monitoramento é uma evolução futura.

No Host e no Viewer, configure um endereço alcançável pela rede de testes:

```powershell
$env:CONECT_RELAY_HOST = "ENDERECO_DO_SEU_RELAY"
Test-NetConnection $env:CONECT_RELAY_HOST -Port 5938
```

Depois inicie os aplicativos conforme o README. O teste de porta verifica conectividade, não autenticação nem funcionamento completo da sessão.

## Operação e custos

O endereço público pode mudar após parar e iniciar a instância, dependendo da configuração. Confira o endereço no console antes de atualizar os clientes. Avalie computação, IPv4, armazenamento e tráfego na sua conta; não foi feita estimativa de custo ou comparação com concorrentes. Encerre recursos de laboratório quando não forem necessários.
