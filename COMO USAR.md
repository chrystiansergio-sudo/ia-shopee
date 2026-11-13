# IA Shopee – como usar

## Ligar e desligar
- **Ligar tudo:** dê dois cliques em `Iniciar IA Shopee.bat`. Ele liga o bot do WhatsApp, o painel (site) e o robô que fabrica e entrega os vídeos. O painel abre sozinho no navegador.
- **Desligar tudo:** `Parar IA Shopee.bat`.
- O computador precisa ficar **ligado** (pode bloquear a tela, mas não desligar nem suspender).

## Abrir o painel
- No computador: http://127.0.0.1:5055
- No celular, **no Wi-Fi de casa**: http://192.168.7.4:5055
- Na primeira vez, use o link de **primeiro acesso** que o Claude passou para criar sua senha.

## Vender um pack
1. **Clientes** → cadastre o cliente (nome, WhatsApp e, se ele tiver, a API de afiliado da Shopee dele).
2. Abra o cliente → escolha o pack (10, 20 ou 30) ou digite a quantidade → escolha o nicho e o robô → **Registrar venda e enviar**.
3. Peça ao cliente para mandar um **"oi"** para o número do robô antes (o WhatsApp bloqueia mensagem para quem nunca conversou).
4. O robô pega vídeos prontos do **estoque**, troca o link pelo link de afiliado do cliente e manda um por um no WhatsApp dele.
   Cada vídeo vai para **um cliente só** e nunca se repete.

## Telas
- **Visão geral:** quanto entrou no mês (setas ◀ ▶ para mês anterior / próximo), a receber, gráfico de 6 meses.
- **Pedidos:** situação de cada entrega (na fila, enviando, entregue).
- **Agentes:** números de WhatsApp que mandam os vídeos. "Adicionar" mostra o QR Code para conectar um número novo.
- **Estoque:** quantos vídeos prontos existem e a meta (o robô fabrica nas horas vagas até chegar nela). Vídeos com mais de 48 h são descartados porque o preço muda.
- **Preços:** os 3 preços dos packs (editáveis) e o seu **pack diário** (horário, quantidade e nicho).

## Suas gravações
- Mande áudios/vídeos do seu WhatsApp pessoal para o número do robô: ele responde "✅ guardado" e salva em `gravacoes/`.
- As frases curtas viram aberturas dos vídeos "homem" e "narrado"; a sua voz também foi clonada (IA Chatterbox) para narrar esses vídeos.

## Como os vídeos são feitos (custo zero por vídeo)
- Produto: **sempre a foto real** da Shopee, parada, com zoom bem lento (a IA nunca mexe no produto).
- Fundo: filmagens **reais** do nicho (Coverr / Pixabay).
- Aberturas: apresentadora/apresentador de IA com a boca sincronizada (Hugging Face PRO), cachorro real, cena real ou direto no produto.
- Antes e depois do preço, selo de desconto, estrelas, vendidos, "toque no produto", selo "Conteúdo gerado com IA" e #publi.

## Chaves (arquivo `.env`, não compartilhe)
Shopee (dono), Pixabay, Coverr, Unsplash, Hugging Face, senha do painel.
