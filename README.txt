CONect PySide6 - cliente e servidor com interface nova

COMO INSTALAR
1. Abra o terminal na pasta do projeto.
2. Instale as dependências:
   pip install -r requirements.txt

COMO RODAR O SERVIDOR
python server.py

COMO RODAR O CLIENTE
python viewer.py

LOGIN DO CLIENTE
usuario: admin
senha: 1234

TESTE EM LAN
1. Rode o server.py na máquina que será acessada.
2. Veja o IP local e a senha mostrados no painel do servidor.
3. Rode o viewer.py na outra máquina.
4. No painel, informe Host/IP remoto e a senha do servidor.
5. Clique em Conectar.

OBSERVAÇÕES
- O protocolo foi mantido: controle na porta 5000 e vídeo na porta 6000.
- A interface foi migrada para PySide6.
- Mouse, teclado e vídeo continuam usando a lógica do projeto funcional.
