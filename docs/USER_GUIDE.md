# Sovereign — User Guide

*A calm, plain-language guide to governing your attention. No technical knowledge required.*

---

## What Sovereign does, in one minute

All day, messages arrive from many places — WhatsApp, Telegram, email, SMS. Most of them are not urgent, but each one still pulls at your attention.

Sovereign sits quietly between those apps and you. It reads every incoming message and asks one question:

> **Does this need to reach me *right now*?**

- If **yes**, it sends you a short text message (SMS) on your simple phone. That's the only time your phone makes a sound.
- If **no**, it keeps the message safe in **the Vault**, where you can read it later, on your own schedule.

Nothing is ever deleted. Nothing is ever lost. You decide what counts as urgent — and Sovereign learns from you over time.

You manage all of this from a calm web page (your "dashboard"), usually at **http://localhost**. You don't need an app on your phone. That's on purpose.

---

## How Sovereign decides: the three gates

Every message passes through three gates, in order. The first gate that says "this is urgent" wins, and the message is sent to your phone immediately. If no gate claims it, the message waits in the Vault.

```
  A message arrives
        │
        ▼
  ┌───────────────┐   Is the sender on your VIP list?
  │ 1. The Council│ ─── yes ──▶  Send to phone
  └───────────────┘
        │ no
        ▼
  ┌───────────────┐   Does it match one of your rules?
  │ 2. The Decrees│ ─── yes ──▶  Send to phone (or deliberately hold)
  └───────────────┘
        │ no
        ▼
  ┌───────────────┐   Does the AI think it's urgent for you?
  │ 3. The Advisor│ ─── yes ──▶  Send to phone
  └───────────────┘
        │ no
        ▼
     The Vault  (held, waiting for you)
```

Think of it like a thoughtful assistant at your front door: first they check your list of close people, then your written house rules, then their own growing sense of what matters to you. Everyone else is asked to leave a note in the tray (the Vault).

---

## The first time you open Sovereign

On first use, Sovereign asks you a single question:

> *Who are the people whose message should always reach you, no matter what, no matter when?*

This becomes your **Council** (your VIP list). For each person you add:

- **Name** — how you'll recognize them, e.g. `Mamá`, `Dr. López`, `Carlos`.
- **Platform** — where they message you from: WhatsApp, Telegram, email, or SMS.
- **Sender ID** — *how that platform identifies them*:
  - Email → their email address, e.g. `mama@gmail.com`
  - SMS / WhatsApp → their phone number with country code, e.g. `+573001234567`
  - Telegram → their `@username` (or numeric ID)

Add a few people and press **Begin**. You can always change this later. Take your time — this list is the heart of Sovereign.

---

## The five rooms

Your dashboard has five "rooms," shown as tabs across the top. Here's what each one is for, how to use it, and when to visit.

---

### 🗄 The Vault — *where held messages wait*

**What it is:** Every message that wasn't urgent enough to reach your phone lands here. It's not a trash can — it's a calm inbox you check when *you* choose to.

**The two tabs:**
- **Waiting** — messages you haven't opened yet.
- **Retrieved** — messages you've already opened.

**How to use it:**
1. Open the **Vault** tab. You'll see a list: sender name, the platform (e.g. `[EM]` for email), and how long ago it arrived.
2. Click **Read** on any message to see its full content. Doing so moves it from *Waiting* to *Retrieved* (like marking an email as read).
3. To reply, use your simple phone — when you expand a message, Sovereign shows you the exact text command to send (see *Replying from your phone* below).

**Tip:** Quietly opening a held message also teaches the Advisor. If you often rush to open messages from a certain person, the Advisor notices and may suggest promoting them.

**When to visit:** Daily, or whenever you have a calm moment — not because a badge is nagging you (there are none).

---

### 👑 The Council — *your VIP list*

**What it is:** The people whose messages **always** reach you, skipping every other check. Small by design.

**How to add someone:**
1. Open **The Council** → click **+ Add member**.
2. Fill in **Platform**, **Name**, and **Sender ID** (same as onboarding above).
3. Optionally tick **"Always deliver, even during quiet hours"** — use this for the few people who should reach you at 3 a.m.
4. Click **Add to Council**.

**To manage members:**
- Toggle the switch next to a member to turn their "always on" (quiet-hours override) on or off.
- Click **Remove** to take someone off the list.

**A gentle limit:** Around 10 members, Sovereign reminds you that *"an unlimited Council is no Council."* It won't stop you — it just nudges you to keep the list meaningful.

**Example:** Add `Mamá` (WhatsApp, `+573001234567`, *always on*) and `Dr. López` (SMS, `+573009998877`). Now anything from either of them reaches your phone instantly, even during quiet hours.

**When to visit:** Rarely — only when your closest relationships change.

---

### 📜 The Decrees — *your rules*

**What it is:** Your personal rulebook. Each Decree is a simple sentence: **IF** *something is true about a message* **THEN** *pass it through* (send to phone) **or** *hold it* (send to Vault).

**The three rules you start with:**
| Rule | What it does |
|---|---|
| **Hold all group messages** | Group chats never reach your phone (you can override). |
| **Urgency keywords** | Messages containing words like *emergency, urgent, hospital* are passed through. |
| **Frequency escalation** | If the same person messages 3+ times in 10 minutes, it's passed through. |

These three are marked **default** and can't be deleted — but you can switch any of them **off** with its toggle.

**How to create your own rule:**
1. Open **The Decrees** → click **+ New Decree**.
2. Give it a **name** you'll recognize, e.g. *"Pass messages from the school."*
3. Choose a **Condition** (what to look for):
   - *Message is in a group*
   - *Message contains keyword* (you then type words separated by commas)
   - *Same sender, high frequency*
   - *Platform is…* (e.g. only email)
   - *Message type is…*
4. Choose an **Action**: **PASS** (send to phone) or **HOLD** (send to Vault).
5. Set a **Priority** number (explained below).
6. Click **Create Decree**.

**How priority works (important):** Decrees are checked from the **lowest number first**, and **the first one that matches wins** — the rest are skipped. So a rule with priority `5` is checked before one with priority `50`.

> **Worked example — silence marketing emails, but never miss the hospital:**
> 1. Create *"Pass hospital"* → Condition: *contains keyword* → `hospital, emergency` → Action: **PASS** → Priority **5**.
> 2. Create *"Hold newsletters"* → Condition: *contains keyword* → `newsletter, sale, unsubscribe` → Action: **HOLD** → Priority **20**.
>
> Because "Pass hospital" has the lower number, a message saying *"hospital sale today"* still reaches you — the urgent rule is checked first.

**When to visit:** Often at first, as you fine-tune your rules; rarely once they feel right.

---

### 🧭 The Advisor — *the AI that learns you*

**What it is:** A private assistant that watches **how you behave** (which held messages you rush to open, which urgent ones you ignore) and slowly learns your personal definition of urgency. It **never reads your message content** — only your patterns.

**What you'll see:**
- A **maturity level** (0 to 4) and how long it's been *watching since*.
- Once it has data: **Signals** (how much it has learned), **Accuracy**, **False passes** (times it bothered you needlessly), and **Missed urgent** (times it held something you actually wanted).
- Occasionally, a **suggestion** — e.g. *"You often open messages from Carlos quickly. Add him to your Council?"* You can tap **Got it** or **Not relevant**.

**The maturity levels:**
| Level | Name | Roughly when | What it does |
|---|---|---|---|
| 0 | Silent | Weeks 1–2 | Just watching. Makes no decisions. |
| 1 | Suggesting | Weeks 3–4 | Starts surfacing gentle suggestions. |
| 2 | Advising | Month 2 | Regular recommendations, fully shown. |
| 3 | Refining | Month 4+ | Can auto-adjust (only if you opt in). |
| 4 | Sovereign | Month 6+ | Fully personalized to you. |

**Your control:** At the bottom is **Reset the Advisor**. This erases everything it has learned and starts from zero, no questions asked. The model is yours.

**Privacy in plain terms:** All of this runs **on your own machine**. Sender names are stored as scrambled codes, not readable text. Nothing is sent to any company.

**When to visit:** Weekly, to glance at suggestions.

---

### 📖 The Chronicle — *your honest history*

**What it is:** A truthful log of every decision Sovereign made — what was passed to your phone, what was held, and why. No scores, no streaks, no gamification. Just the facts.

**What you'll see:**
- **Totals** for the period: how many messages total, how many passed, how many held.
- A **By platform** breakdown (e.g. how much came from email vs. Telegram).
- A list of **Recent decisions**, each showing the sender, the platform, the decision (pass/hold), and which gate made the call (Council, Decrees, or Advisor).

This room is **read-only** — it's for reflection, not configuration. It's where you go to answer *"Wait, did I miss something?"* — and reassure yourself that you didn't.

**When to visit:** Weekly, or any time you're curious where your attention actually went.

---

## Replying from your simple phone (SMS commands)

When an urgent message reaches your phone, you have a **15-minute window** to simply **text back your reply** — Sovereign routes it to the right person on the right platform, invisibly. To them, it's a normal conversation.

After the window, or to do more, use these short commands (just text them to Sovereign's number):

| You text… | What happens |
|---|---|
| `r Sounds good, talk soon` | Reply to the **most recent** urgent message |
| `r mama I'll be home at 6` | Reply to the last message from the contact named **mama** |
| `r 2 On my way` | Reply to the **2nd** most recent message |
| `list` | See a numbered list of recent held messages |
| `read 3` | Read the full text of message **#3** |
| `status` | Get a quick summary of your Vault |

Sovereign texts back a short confirmation after each command, so you always know it worked.

---

## Quiet hours

Quiet hours let messages wait quietly overnight, even if they'd normally reach your phone. During quiet hours, only Council members with **"Always deliver"** turned on can wake you.

In this version, the **per-person override** is set in **The Council** (the *"Always deliver, even during quiet hours"* toggle). The overall quiet-hours window is an advanced setting configured by whoever set up your Sovereign — ask them if you'd like it adjusted.

---

## A few everyday scenarios

**"I want my mother to always reach me, day or night."**
→ The Council → Add her → tick *Always deliver, even during quiet hours*. Done.

**"Group chats are driving me crazy."**
→ They're already held by default (the *Hold all group messages* Decree). Nothing to do. To let one specific person in a group through, add **them** to your Council.

**"Marketing emails keep reaching my phone as 'urgent'."**
→ This usually means they contain a keyword like *urgent*. Two options: (1) in **The Decrees**, open *Urgency keywords* and trim the keyword list, or (2) add a higher-priority **HOLD** rule for words like *sale, newsletter, promo*. Check **The Chronicle** to see which rule passed them.

**"I think Sovereign held something important."**
→ Open **The Vault → Waiting**, or text `list` from your phone. Nothing is ever lost — it's there.

---

## Frequently asked questions

**Will people know their message was filtered or held?**
No. Sovereign is invisible. From their side, you simply replied (or haven't yet) — a normal conversation.

**Does Sovereign read my messages?**
The filtering needs to see message text to match your keyword rules, but it runs entirely on your own machine. The **Advisor** never stores message content — only your behavior patterns, as scrambled codes.

**What if I set up a rule wrong?**
Nothing breaks. Worst case, a message goes to the Vault instead of your phone (or vice-versa). Adjust the Decree and you're set. Check the Chronicle to see what happened.

**Can I start over?**
Yes — reset the Advisor from its room, edit or disable any Decree, and add/remove Council members any time. It's your Realm.

---

*Sovereign. Govern your attention.*
