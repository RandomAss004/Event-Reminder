# Event Reminder — with automatic WhatsApp (Twilio)

This folder is a complete, deployable version of the app:
- `index.html` — the web app (same one you have on the Claude link)
- `api/send-whatsapp.js` — a tiny backend that sends the WhatsApp message via Twilio
- Your Twilio keys live only as environment variables on the hosting platform, never in the code

When this is deployed together (index.html + api/), the app calls its own
`/api/send-whatsapp` automatically when a reminder fires — no manual tap needed.
If that call fails for any reason, it quietly falls back to a "Send WhatsApp reminder"
button, so the app never breaks.

## 1. Set up Twilio (5 min)

1. Create a free account at https://www.twilio.com/try-twilio
2. In the Twilio Console, go to **Messaging → Try it out → Send a WhatsApp message**.
   This activates the **WhatsApp Sandbox** and gives you:
   - A sandbox number, usually `+1 415 523 8886`
   - A join code like `join xxxx-xxxx`
3. **This is the step most people miss and get "bugs" from:** the sandbox can only
   message numbers that have joined it. From the WhatsApp of every phone number you
   want to remind (yours, your friends'), send that exact `join xxxx-xxxx` text to
   the sandbox number on WhatsApp. Until they do this, Twilio will fail to deliver.
   (For a real product later, you'd apply for a Twilio-approved WhatsApp Business
   number, which can message anyone without this join step.)
4. From the Console dashboard, copy your **Account SID** and **Auth Token**.

## 2. Push this folder to GitHub

Create a new repository and push these files (Account SID/Token do **not** go
in any file here — only in Vercel's dashboard in step 3).

## 3. Deploy on Vercel (free)

1. Go to https://vercel.com → sign up → **Add New Project** → import your GitHub repo.
2. Before the first deploy, open **Settings → Environment Variables** and add:
   | Name | Value |
   |---|---|
   | `TWILIO_ACCOUNT_SID` | from Twilio console |
   | `TWILIO_AUTH_TOKEN` | from Twilio console |
   | `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` (your sandbox number) |
3. Deploy. Vercel gives you a public URL like `https://your-app.vercel.app` —
   this is the link anyone can open, no Claude account needed.
4. Open that URL, register/login, add an event with a phone number that has
   joined your sandbox, and set the time a couple of minutes out to test.

## Notes

- The Claude-hosted link you already have will keep working exactly as before
  (manual "Send WhatsApp" tap) — it can't reach this backend by design, since
  that page is sandboxed for security. This Vercel link is the one with
  automatic sending.
- Twilio's WhatsApp Sandbox is meant for testing. Messages there also carry a
  short Twilio disclaimer text and recipients must rejoin the sandbox roughly
  every 72 hours of inactivity. For a permanent, disclaimer-free number, apply
  for WhatsApp Business API access through Twilio (takes a few days, needs a
  Meta Business verification).
- Free tier limits: Twilio trial accounts have a small message credit; Vercel's
  free tier is generous enough for a personal reminder app.
