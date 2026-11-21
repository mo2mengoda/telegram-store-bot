# Telegram Store Bot

An Arabic shop assistant bot for small online stores. Customers browse products and place orders inside Telegram. Every order is saved, and the store owner gets an instant alert.

## Features
- Main menu: Products · Order now · Contact · About
- Product catalogue with details and prices, loaded from `products.json` (no code changes needed to edit it)
- Step-by-step order flow: product → quantity → name → phone → address → confirm
- Input validation, including Arabic digits (٠١٢٣) and phone format
- Orders saved to `orders.csv` (opens directly in Excel)
- Instant order notification to the owner
- Owner-only `/stats` command for order count and revenue
- `/cancel` at any step

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env      # add your BOT_TOKEN from @BotFather
python bot.py
```
Send `/id` to the bot to get your chat ID, put it in `ADMIN_CHAT_ID`, and restart.

## Tech
Python · python-telegram-bot v21 (async) · ConversationHandler · CSV storage

> Can be extended with a Google Sheets/database backend, payment links, order tracking, or an admin panel.
