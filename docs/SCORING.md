# Scoring and Filtering Rules

`jyamzon` uses rule-based scoring to create a first-pass shortlist. Scores are not a substitute for market data.

## Hard Exclusions

The filtered workflow excludes candidates when the title, brand, category path, or bullets suggest:

- major brand or platform ecosystems: Apple, Samsung, Sony, Microsoft, Nintendo, Google, Sonos, Disney, Starlink, and similar
- strong standardized products: phones, laptops, desktops, servers, tablets, SSDs, RAM, cameras as primary products, printers/scanners where not treated as reject examples
- service or non-physical products: warranty, replacement plan, installation service, license, digital code, game/software edition
- missing critical scrape fields: no title or no image

## Positive Signals

Products score better when they are:

- light accessories or small peripherals
- in a $15-$60 price range
- not heavily review-moated
- easy to differentiate with material, color, bundle, compatibility, packaging, or use-case positioning
- naturally suited to Chinese supply chains

Examples:

- cable organizer bags
- camera straps
- phone/e-reader holders
- mount hardware kits
- small carrying cases
- laptop bags or accessory totes

## Risk Penalties

The score is downgraded when products involve:

- wireless/Bluetooth/Wi-Fi/radio features
- battery, charger, power strip, surge protector, or AC adapter safety risk
- security/surveillance privacy risk
- high return/defect categories such as audio players, speakers, printers, or complex electronics
- strong commodity competition such as generic cables, screen protectors, and simple adapters

## Score Meaning

| Score | Meaning |
|---:|---|
| 78-100 | Worth priority research |
| 65-77 | Worth secondary validation |
| 50-64 | Cautious; needs better data |
| 0-49 | Do not prioritize |

## Required Follow-Up Data

Before spending product-development money, validate:

- search volume
- monthly purchases
- PPC bid
- purchase rate
- product concentration
- brand concentration
- review moat
- estimated monthly sales/revenue
- compliance and IP risk

