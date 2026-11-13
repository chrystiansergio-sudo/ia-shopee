# IA Shopee – instalar em outro computador (Windows)

## 1. Programas (uma vez só)
Instale, aceitando as opções padrão:
- **Python 3.12** – https://www.python.org/downloads/ (marque **"Add python.exe to PATH"**)
- **Node.js 24 LTS** – https://nodejs.org
- **FFmpeg** – no Prompt de Comando: `winget install Gyan.FFmpeg`
- **Google Chrome** (usado para desenhar os vídeos)
- **Git** – https://git-scm.com

## 2. Baixar o projeto
```
git clone https://github.com/chrystiansergio-sudo/ia-shopee.git
cd ia-shopee
pip install -r requirements.txt
cd whatsapp && npm install && cd ..
```

## 3. Chaves (cada um usa as suas)
Copie `.env.example` para `.env` e preencha:
- `DONO_SHOPEE_APP_ID` e `DONO_SHOPEE_SECRET`: sua API de afiliado da Shopee (os links saem com a SUA comissão).
- `SITE_SECRET` e `SITE_TOKEN`: invente dois textos longos (ex.: 40 letras e números aleatórios).
- As outras são opcionais.

## 4. Ligar
Dois cliques em **`Iniciar IA Shopee.bat`**. Abre o painel em http://127.0.0.1:5055

- **Primeira senha:** abra `http://127.0.0.1:5055/primeiro-acesso/SEU_SITE_TOKEN` (o mesmo texto que você colocou no `.env`).
- **WhatsApp:** no painel, vá em **Agentes** → adicionar → leia o QR Code com o WhatsApp que vai mandar os vídeos.

Depois, veja o **`COMO USAR.md`**.

## Observações
- Cada computador tem o seu próprio painel, clientes e estoque (os dados não sobem pro GitHub).
- O computador precisa ficar ligado enquanto o robô trabalha.
