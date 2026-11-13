@echo off
rem Desliga o bot, o painel e o robo do IA Shopee (so as janelas deste projeto).
taskkill /fi "WINDOWTITLE eq IA Shopee - WhatsApp*" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq IA Shopee - Painel*" /t /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq IA Shopee - Robo*" /t /f >nul 2>&1
echo IA Shopee desligado.
timeout /t 3 >nul
