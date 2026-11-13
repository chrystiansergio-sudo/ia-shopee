@echo off
rem Liga tudo do IA Shopee: bot de WhatsApp, painel (site) e o robo que faz e entrega os videos.
cd /d "%~dp0"
if not exist dados mkdir dados
echo Ligando o bot de WhatsApp...
start "IA Shopee - WhatsApp" /min cmd /c "cd /d "%~dp0whatsapp" && node bot.mjs >> ..\dados\bot.log 2>&1"
timeout /t 5 >nul
echo Ligando o painel (site)...
start "IA Shopee - Painel" /min cmd /c "cd /d "%~dp0site" && python app.py >> ..\dados\site.log 2>&1"
echo Ligando o robo dos videos (prioridade baixa)...
start "IA Shopee - Robo" /min /low cmd /c "cd /d "%~dp0motor" && python trabalhador2.py >> ..\dados\robo.log 2>&1"
timeout /t 4 >nul
start "" http://127.0.0.1:5055
echo.
echo Pronto! O painel abriu no navegador.
echo No celular (mesmo Wi-Fi de casa): http://192.168.7.4:5055
echo Para desligar tudo, use "Parar IA Shopee.bat".
timeout /t 8 >nul
