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

## Correção da falha de QtCore nos executáveis

A falha relatada pelo autor foi reproduzida nos dois executáveis anteriores. Manter o processo aberto no teste anterior não comprovava a criação da janela: ele podia estar parado na caixa de erro do carregador.

A análise de dependências identificou uma `icuuc.dll` de uma instalação externa de Poppler coletada pelo PATH do ambiente de compilação. Essa biblioteca não exportava `ucnv_open`, `ucnv_close` e `ucnv_reset`, entre outras funções exigidas pelo Qt6Core. A ICU do Windows oferece essas funções.

Os arquivos `.spec` agora limpam o PATH usado na análise, excluem as cópias externas de ICU e unificam o runtime MSVC. PySide6 e Shiboken continuam na versão 6.11.0.

Validação dos novos `Conect-Host-Corrigido.exe` e `Conect-Viewer-Corrigido.exe`:

- Executados os próprios arquivos únicos gerados pelo PyInstaller.
- Saída com código zero e relatório de diagnóstico com `status: ok` em ambos.
- Qt 6.11.0 carregado e janelas criadas usando o plugin `windows` (sem exibição durante o diagnóstico).
- Campo de servidor confirmado como `ec2-15-228-9-137.sa-east-1.compute.amazonaws.com`.
- A análise dos pacotes confirmou ausência de ICU/Poppler externos.

A validação comprova a inicialização neste Windows. Não comprova a conectividade da EC2, uma sessão remota entre máquinas ou compatibilidade com todas as versões de Windows.
