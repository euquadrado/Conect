# Segurança, limitações e validação

## Limitações observadas no código

- TCP sem TLS: credenciais, imagens e comandos não têm criptografia implementada pelo aplicativo.
- Senha numérica de quatro dígitos, gerada com `random`, sem limitação de tentativas.
- O relay mantém a senha em memória e não autentica a identidade do servidor para os clientes.
- `hosts.pop` remove o Host antes de validar a senha do Viewer. Uma tentativa incorreta pode impedir novas conexões até o Host se registrar novamente.
- Registro com ID repetido substitui a conexão anterior.
- Leitura de pacotes sem limite explícito de tamanho e leitura inicial sem prazo no servidor.
- O compartilhamento é iniciado pelo Host, mas não há uma aprovação adicional por Viewer após o envio das credenciais.
- `pyautogui.FAILSAFE` está desativado; encerre o compartilhamento na interface e mantenha um meio local de interrupção.
- Não há evidência de auditoria persistente, revisão independente de segurança ou suporte a sessões concorrentes por Host.

Use apenas em laboratório autorizado, com dados de teste e rede controlada. O código não deve ser apresentado como pronto para atendimento corporativo em produção.

## Validação desta publicação

Consulte `VALIDATION.md` para os testes efetivamente executados. Não foram comprovados o estado da antiga EC2, o desempenho entre máquinas, a execução dos binários originais ou a segurança para produção.

## Roteiro manual entre duas máquinas

1. Inicie o relay em uma rede privada de teste e configure os dois clientes.
2. Ative o Host e conecte o Viewer com as credenciais exibidas.
3. Confira imagem, movimento, cliques, rolagem, digitação e teclas especiais em um editor vazio.
4. Teste troca de monitor e telas com escalas diferentes.
5. Encerre pelo Host e confirme que o controle para.
6. Teste senha incorreta, desconexão e novo registro do Host.
7. Registre ambiente, versões, resultados e falhas antes de divulgar uma demonstração.
