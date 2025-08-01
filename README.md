# Liquidation Rebound Bot

A Telegram bot that detects Bitcoin liquidation-driven price rebounds using AI and technical logic.

## Key Commands

/start - Register  
/menu or /help - View command list  
/backtest - Simulate 7 days of trades  
/last10 - Show last 10 live trades  
/train - Learn from past signals  
/logs - Show recent trade logs  
/status - Show strategy thresholds  
/liqcheck - Test Coinglass API  
/news - Bitcoin headlines

## Environment Setup

- TELEGRAM_BOT_TOKEN = your Telegram bot token  
- WEBHOOK_URL = https://your-service.onrender.com

## Timezone

All timestamps shown in Indian Standard Time (IST).

## Learning

Bot adapts using wins, losses, RSI, wick, liquidation size, funding, and news data.