# Atrium experience restructure: design

Approved 12 Oct 2026. Visual reference: the Claude Design canvas "Atrium redesign" (front door on desktop and phone, Priya's home, Daniel's leads, Mei's reconciliation, Omar's alert).

## Why

Someone opening the live link cannot tell what Atrium is, whose shoes they are in, or what to try. Staff see every workspace stacked in one sidebar, investors see ten links, and pages open with paragraphs instead of the thing that matters.

## Who it is for

Judges seeing Atrium cold, with minutes rather than hours. It stays a working product underneath: every feature and API from Plans 1 to 5 keeps working.

**Success:** within a minute a newcomer knows what Atrium is, who they are, and what to try next, and every screen reads at a glance.

## Decisions

1. **A story-led front door** at `/`, in place of the persona list:
   - one sentence on what Atrium is;
   - a floor plan of four rooms (Acquire, Invest, Trade, Operate) around a lit well, the shared ledger and AI decision log, each room naming its AI moment;
   - "What the AI does, and what it never does": it explains while the engines count, it proposes while people decide, and it shows where it looked;
   - "Choose a person": the eight personas grouped by stage, each with a one-line story, two things to try and an Enter button; Priya is marked "start here".

   With Firebase sign-in, `/login` keeps the email form.
2. **One shell for everyone:**
   - a top bar with the wordmark, the four stages with the person's own lit, "Ask Atrium" for investors (the Copilot) and a person chip linking to "Switch person";
   - a left rail with only the person's own workspace, at most five items with icons;
   - a journey guide on the right.

   Below 1180 px the guide moves under the page; below 760 px the rail becomes a horizontal strip under the top bar.
3. **Journeys.** Each persona has three or four numbered steps, each with a target page and a short line. A step is done once its page has been visited (kept in the browser's local storage per persona); the first undone step is "now" and gets a button. The guide can be hidden and shown again.
4. **Navigation regrouped.** Sections may have tabs shown at the top of the page; routes do not change.

   | Persona | Sections (tabs) |
   |---|---|
   | Investors | Home; Portfolio (X-ray, Risk, Risk profile); Markets (Markets, Your trades); Funds (Funds, Fund orders); Plan ahead. The Copilot opens from "Ask Atrium". |
   | Advisor | Leads; Held orders; Prospect form |
   | Operations | Today; Reconciliation; Approvals; Blotter |
   | Compliance | Alerts; Decision log |

5. **Page anatomy.** Each page opens with its key moment: a headline sentence and the visual that proves it. Detail follows, and actions are plain-English buttons. Restructured to the canvas:
   - Investor home: the "one thing needs your attention" panel with the risk scale.
   - Leads: "look at these first", then "worth a call".
   - Reconciliation: the statement's counts and balance check, the agent's proposals as statement-to-subscription pairs, "accept all exact matches", and what is left.
   - An alert: the finding as a headline, a chart of the payments against the $10,000 line for structuring, the case review beside who is linked and the decision.
   - Every other page adopts the shell, the tabs, the kit and shorter headers.
6. **The AI's voice.**
   - Gemini's words are set in Source Serif 4.
   - A caption with a small daylight square names the model and says the figures were checked.
   - Citations are small chips.
   - The coloured left rule goes.
7. **Look ("Atrium Daylight"):**
   - **Colour:** porcelain ground `#F1F3F1`, white surfaces, ink `#0F1B24`. Daylight amber `#E3A72F` is reserved for AI and explanation.
   - **Status colours:** gain `#157347`, loss `#B23A26`, caution `#8A5A00`; the five band colours stay.
   - **Type:** Archivo, expanded for headlines and tabular for figures.
   - **Shape:** 18 px panels and pill buttons at least 44 px tall.
   - **Motion:** only in answer to an action.

## Out of scope

- API changes.
- The deck, the video and the production demo-data reset (still Plan 6).

## Testing

- **Unit tests:** the journey and navigation logic is pure and unit-tested with Vitest.
- **Gates:** `tsc --noEmit`, lint and Vitest on every task.
- **Visual check:** screenshots of every page at 1280 and 390 px, with no horizontal page scroll at 390.
- **After deploy:** a check of the live site.
