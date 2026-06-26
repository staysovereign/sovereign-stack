const TelegramBot = require('node-telegram-bot-api');
const { dispatch, buildMessage } = require('../shared/normalize');

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!TOKEN) throw new Error('TELEGRAM_BOT_TOKEN is required');

const bot = new TelegramBot(TOKEN, { polling: true });

function contentTypeFromMsg(msg) {
  if (msg.text) return { type: 'text', body: msg.text };
  if (msg.voice) return { type: 'voice', media_url: msg.voice.file_id, duration_seconds: msg.voice.duration };
  if (msg.photo) return { type: 'image', media_url: msg.photo.at(-1).file_id };
  if (msg.video) return { type: 'video', media_url: msg.video.file_id };
  if (msg.document) return { type: 'document', media_url: msg.document.file_id };
  if (msg.sticker) return { type: 'sticker', media_url: msg.sticker.file_id };
  return { type: 'text', body: '[unsupported message type]' };
}

bot.on('message', async (msg) => {
  const from = msg.from || {};
  const chat = msg.chat;

  const isGroup = chat.type === 'group' || chat.type === 'supergroup';

  const normalized = buildMessage({
    platform: 'telegram',
    sender: {
      id: String(from.id),
      name: [from.first_name, from.last_name].filter(Boolean).join(' ') || from.username || null,
      phone: null,
    },
    content: contentTypeFromMsg(msg),
    group: isGroup ? String(chat.id) : null,
    metadata: {
      chat_id: String(chat.id),
      message_id: msg.message_id,
      username: from.username || null,
    },
  });

  try {
    await dispatch(normalized);
  } catch (err) {
    console.error('[telegram] dispatch failed:', err.message);
  }
});

bot.on('polling_error', (err) => {
  console.error('[telegram] polling error:', err.message);
});

console.log('[telegram] connector started, polling...');

module.exports = { bot };
