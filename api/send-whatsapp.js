// Vercel serverless function: POST /api/send-whatsapp
// Body: { "to": "+91XXXXXXXXXX", "message": "Reminder: ... is now." }
//
// Credentials are read from environment variables ONLY (set them in the
// Vercel dashboard, never write them into this file or commit them to git).
//   TWILIO_ACCOUNT_SID
//   TWILIO_AUTH_TOKEN
//   TWILIO_WHATSAPP_FROM   e.g. "whatsapp:+14155238886" (sandbox number)

const twilio = require('twilio');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { to, message } = req.body || {};
  if (!to || !message) {
    return res.status(400).json({ error: '"to" and "message" are required' });
  }

  const accountSid = process.env.TWILIO_ACCOUNT_SID;
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  const fromNumber = process.env.TWILIO_WHATSAPP_FROM;

  if (!accountSid || !authToken || !fromNumber) {
    return res.status(500).json({ error: 'Server is missing Twilio environment variables' });
  }

  // Normalize the destination number to E.164 (digits only, leading +)
  let toDigits = String(to).replace(/[^\d+]/g, '');
  if (!toDigits.startsWith('+')) toDigits = '+' + toDigits;

  try {
    const client = twilio(accountSid, authToken);
    const result = await client.messages.create({
      from: fromNumber.startsWith('whatsapp:') ? fromNumber : `whatsapp:${fromNumber}`,
      to: `whatsapp:${toDigits}`,
      body: message,
    });
    return res.status(200).json({ sid: result.sid, status: result.status });
  } catch (err) {
    console.error('Twilio send error:', err.message);
    return res.status(500).json({ error: err.message || 'Failed to send WhatsApp message' });
  }
};
