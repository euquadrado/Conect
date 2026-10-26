# Validação executada em 26/10/2026

- Análise sintática de todos os arquivos Python: passou.
- Comparação das três cópias do protocolo: idênticas.
- Relay iniciado localmente com Python 3.10: passou.
- Registro de Host e autenticação de Viewer: passaram.
- Encaminhamento de pacote sintético de imagem Host → Viewer e comando Viewer → Host: passou.
- Rejeição de registro inválido e Viewer com ID inexistente: passou.

Os testes usam sockets locais e dados sintéticos. Não validam captura real, controle de uma segunda máquina, interação gráfica, implantação EC2, desempenho, executáveis ou segurança em produção. Os defeitos descritos em SECURITY.md permanecem nesta versão.

## Configuração do servidor na interface

- Host e Viewer: abertura das janelas em modo offscreen e criação dos campos passaram.
- Salvamento e recuperação do endereço em uma nova janela passaram, com armazenamento isolado para o teste.
- Campos vazios, URL com caminho, IPv4 inválido e endereço com porta foram rejeitados.
- Executáveis Windows gerados com PyInstaller em modo arquivo único.
- Não foi validada uma sessão remota entre duas máquinas nem a disponibilidade da EC2.
