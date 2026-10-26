# Validação executada em 26/10/2026

- Análise sintática de todos os arquivos Python: passou.
- Comparação das três cópias do protocolo: idênticas.
- Relay iniciado localmente com Python 3.10: passou.
- Registro de Host e autenticação de Viewer: passaram.
- Encaminhamento de pacote sintético de imagem Host → Viewer e comando Viewer → Host: passou.
- Rejeição de registro inválido e Viewer com ID inexistente: passou.

Os testes usam sockets locais e dados sintéticos. Não validam captura real, controle de uma segunda máquina, interação gráfica, implantação EC2, desempenho, executáveis ou segurança em produção. Os defeitos descritos em SECURITY.md permanecem nesta versão.
