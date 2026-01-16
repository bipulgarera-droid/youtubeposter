# YouTube Metadata Style Guide

> Tags and descriptions based on Chill Financial Historian videos.
> Use this directive when generating video metadata.

---

## Tag Structure

**Total tags:** 25-35 per video

### Tag Categories:

1. **Primary Topic (3-5 tags)**
   - Main subject: `France`, `petrodollar`, `Venezuela`, `Greenland`
   - Specific aspect: `French economy`, `Italian debt crisis`, `hyperinflation`

2. **Related Concepts (5-8 tags)**
   - Economic terms: `GDP`, `inflation`, `recession`, `stagflation`
   - Geopolitical terms: `geopolitics`, `sanctions`, `trade war`
   - Financial terms: `debt`, `currency`, `central bank`

3. **Searchable Phrases (5-8 tags)**
   - Question formats: `why France is poor`, `why italy can't grow`
   - Comparison formats: `France vs USA`, `US vs EU economy`
   - Framing: `economic collapse`, `crisis explained`

4. **Trending/Discovery (3-5 tags)**
   - Year: `investing 2025`, `recession 2026`
   - Current events: `breaking news`, `news today`
   - Platform categories: `documentary`, `economics`, `finance`

5. **Long-tail Keywords (5-10 tags)**
   - Very specific: `BASF China`, `Maduro arrested`, `Project Iceworm`
   - Local terms: `smicardization`, `bodegón`, `GIUK gap`
   - Person names: `Emmanuel Macron`, `Nicolas Maduro`, `Mario Draghi`

---

## Tag Examples by Topic Type

### Country Economic Crisis:
```
[Country], [Country] economy, why [country] is failing, [country] GDP,
[country] debt crisis, economics, geopolitics, recession, 
[country] demographics, brain drain, economic collapse, business,
finance, euro, european union, documentary, financial education
```

### Geopolitical Event:
```
[subject], [subject] explained, geopolitics, military strategy,
world war 3, [country] foreign policy, history, economics,
sanctions, international relations, strategic defense, 
documentary, video essay
```

### Currency/Financial System:
```
[currency/system], [currency] collapse, de-dollarization, 
macroeconomics, federal reserve, financial crisis, 
economic collapse, fiat currency, inflation, recession,
investing 2025, money printing, global reset
```

---

## Description Structure

### Format:
```
[Hook Question or Statement - 1-2 sentences]

[Context paragraph - What we cover and why it matters]

In this video, we cover:
[Emoji] [Point 1]: [Subtitle]
[Emoji] [Point 2]: [Subtitle]
[Emoji] [Point 3]: [Subtitle]
[Emoji] [Point 4]: [Subtitle]
[Emoji] [Point 5]: [Subtitle]

CHAPTERS/Timestamps:
[Auto-generated from SRT]

#[Hashtag1] #[Hashtag2] #[Hashtag3] ... (5-10 hashtags)

[Optional: Disclaimer for financial content]
```

### Emojis Used:
- 📉 Decline/drop
- 🏭 Industry/manufacturing
- 👶 Demographics/population
- 💻 Tech/innovation
- ⚡ Energy
- 💸 Money/capital
- 📊 Data/statistics
- ⚠️ Warning/danger
- 🗳️ Politics/voting
- 🇺🇸 🇫🇷 Country flags

---

## Hook Patterns

### Question Hook:
- "Is the US Dollar's 50-year reign finally over?"
- "Why has the European economy stagnated while the US skyrocketed?"

### Statement Hook:
- "Yesterday, history changed. Nicolás Maduro is in U.S. custody."
- "When the United States floated the idea of buying Greenland, the world laughed."

### Contrast Hook:
- "France is the world's most visited country, famous for luxury. But behind the postcard image lies a brutal economic reality."
- "Italy was once the 5th largest economy. Today, it's the only developed nation that hasn't grown in 20 years."

---

## Hashtags (End of Description)

Always include 5-10 hashtags at the end:
```
#Geopolitics #Economics #Finance #[Country] #[MainTopic]
```

Common hashtags:
- #Economics #Geopolitics #Finance
- #Business #History #Documentary
- #Investing #MacroEconomics #GlobalEconomy

---

## Implementation Notes

1. **Tags are comma-separated, lowercase**
2. **Description uses markdown-style formatting**
3. **Timestamps are auto-generated from SRT file**
4. **Hashtags go at the very end**
5. **Include disclaimer for financial content**

---

## Template Prompt for Generation

```
Generate YouTube metadata for a video:

TITLE: [title]
TOPIC: [topic]
COUNTRY: [country if applicable]

Generate:
1. 30 tags (comma-separated, from specific to broad)
2. Description with:
   - Hook (question or bold statement)
   - Context paragraph
   - 5 bullet points with emojis
   - "CHAPTERS:" placeholder
   - 8 hashtags
   - Disclaimer if financial content
```
