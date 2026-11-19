"""
build_seed_data.py - writes the curated seed dataset to data/raw/.

WHY THIS EXISTS: darglobal.co.uk (Imperva Incapsula) and wasalt.sa (Cloudflare) block
automated scrapers, so scrape.py cannot reliably collect their pages. This file holds
content taken from the PUBLIC pages (collected 2026-11-19) in a form the pipeline can use.
Re-run it after editing, then run process_data.py.
"""
import json, os
from collections import Counter

B = "https://darglobal.co.uk"
TS = "2026-11-19"

# (title, location, country, path, tagline)
P = [
("Trump International Hotel & Tower Dubai","Dubai, UAE","United Arab Emirates (UAE)","/trump-international-hotel-and-tower-dubai",""),
("D-Villas At Jumeirah Golf Estates","Dubai, UAE","United Arab Emirates (UAE)","/d-villas-at-jge",""),
("The Astera, Interiors by Aston Martin","Al Marjan Island, RAK, UAE","United Arab Emirates (UAE)","/the-astera",""),
("DG1","Dubai, United Arab Emirates","United Arab Emirates (UAE)","/dg1",""),
("Da Vinci Tower, Interiors By Pagani","Dubai, United Arab Emirates","United Arab Emirates (UAE)","/davinci-tower-by-pagani",""),
("Urban Oasis by Missoni","Dubai, United Arab Emirates","United Arab Emirates (UAE)","/urban-oasis-by-missoni",""),
("W Residences","Dubai, United Arab Emirates","United Arab Emirates (UAE)","/w-residences",""),
("The Pagani Penthouse","Dubai, UAE","United Arab Emirates (UAE)","/one-of-one/project-pagani",""),
("Top of the Astera","Al Marjan Island, RAK, UAE","United Arab Emirates (UAE)","/one-of-one/top-of-the-astera",""),
("Tierra Viva, Design inspired by Automobili Lamborghini","Benahavís, Spain","Spain","/tierra-viva",""),
("Painite Villas Design Inspired by Automobili Lamborghini","Benahavís, Spain","Spain","/one-of-one/painite-villas-design-inspired-by-Automobili-Lamborghini",""),
("Marea, Interiors by Missoni","Cortesin, Spain","Spain","/marea",""),
("Les Vagues by Elie Saab","Doha, Qatar","Qatar","/les-vagues",""),
("Trump International Simaisma, Qatar","Simaisma, Qatar","Qatar","/lp/trump-international-qatar",""),
("Trump International Hotel, Oman","Muscat, Oman","Oman","/aida-trump-international-hotel",""),
("Trump Cliff Villas","Muscat, Oman","Oman","/aida-trump-international-cliff-villas",""),
("Trump Golf Villas","Muscat, Oman","Oman","/aida-trump-villas",""),
("Aida","Muscat, Oman","Oman","/landing-page/aida","One of the world's largest premium mixed-use developments (masterplan)."),
("Fairway Villas","Aida, Oman","Oman","/fairway-villas-aida-oman",""),
("Azure Oceanfront Villas Interiors by Fendi Casa","AIDA, Oman","Oman","/one-of-one/fendi-casa-azure-oceanfront-villas",""),
("Amour Sans Detour","AIDA, Muscat, Oman","Oman","/amour-sans-detour",""),
("The Great Escape","Aida, Oman","Oman","/the-great-escape-1-aida-oman",""),
("The Great Escape 2","Aida, Oman","Oman","/the-great-escape-2-aida-oman",""),
("Coastal Investment Villas","Muscat, Oman","Oman","/aida-coastal-investment-villas",""),
("Sunrise Haven","AIDA, Muscat, Oman","Oman","/Sunrise-Haven-Luxury-Villas",""),
("Marriott Residences","Aida, Oman","Oman","/marriott-residences-aida-oman",""),
("Amour Sans Detour 2","AIDA, Muscat, Oman","Oman","/amour-sans-detour-2",""),
("Nickelodeon Hotels & Resorts","AIDA, Oman","Oman","/play-project/nickelodeon",""),
("The Mulliner","149 Old Park Lane, London, United Kingdom","United Kingdom","/the-mulliner",""),
("7&8 Albert Hall Mansions","Overlooking Hyde Park, London, England","United Kingdom","/one-of-one/THE-ALBERT-HALL-MANSION",""),
("Trump Park Residences","Amaya, Jeddah, KSA","Saudi Arabia (KSA)","/trump-plaza/park-residences",""),
("Trump Mansions","Rayana, Wadi Safar, Riyadh, Saudi Arabia","Saudi Arabia (KSA)","/rayana/trump-mansions","Trump branded residences."),
("Trump Executive Residences","Amaya, Jeddah, KSA","Saudi Arabia (KSA)","/trump-plaza/executive-residences","Premium furnished Trump residences."),
("Amaya","Amaya, Jeddah, KSA","Saudi Arabia (KSA)","/amaya/amaya-plots","Luxury plots in Amaya, Jeddah."),
("Padel Living Residences","Jeddah, KSA","Saudi Arabia (KSA)","/amaya/padel-living",""),
("Neptune, Interiors by Mouawad","Riyadh, KSA","Saudi Arabia (KSA)","/neptune",""),
("Trump Tower Jeddah","Jeddah, KSA","Saudi Arabia (KSA)","/trump-tower-jeddah",""),
("DarGlobal Mansions Interiors by Fendi Casa","Wadi Safar, Riyadh, Saudi Arabia","Saudi Arabia (KSA)","/rayana/darglobal-mansions-fendi-casa",""),
]
PARTNERS = [("Aston Martin","Aston Martin"),("Lamborghini","Automobili Lamborghini"),("Missoni","Missoni"),
            ("Elie Saab","Elie Saab"),("Fendi","FENDI Casa"),("Pagani","Pagani"),("Mouawad","Mouawad"),
            ("Trump","The Trump Organization"),("Marriott","Marriott"),("W Residences","W Hotels / Marriott"),
            ("Nickelodeon","Nickelodeon (Paramount)")]


def ptype(t, tag):
    s = (t + " " + tag).lower()
    for k, v in (("penthouse","Penthouse"),("villa","Villas"),("mansion","Mansions"),("hotel","Hotel"),
                 ("tower","Tower"),("residence","Residences"),("plot","Plots")):
        if k in s:
            return v
    return ""


def doc(source, title, url, text, country=""):
    return dict(source=source, listing_type="info", url=url, title=title, location="", country=country,
                property_type="", price="", description=text, detail_text="", scraped_at=TS)


def write(name, rows):
    os.makedirs("data/raw", exist_ok=True)
    with open(os.path.join("data/raw", name), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{name}: {len(rows)} records")


projects = []
for t, loc, ctry, path, tag in P:
    part = [v for k, v in PARTNERS if k.lower() in t.lower()]
    d = f"{t} is a DarGlobal project located in {loc} ({ctry})."
    if tag:
        d += f" {tag}"
    if part:
        d += f" Brand/design partner named in the project title: {', '.join(dict.fromkeys(part))}."
    d += " The projects listing page does not show price, unit sizes or bedroom counts; see the project page for details."
    projects.append(dict(source="darglobal", listing_type="project", url=B + path, title=t, location=loc,
                         country=ctry, property_type=ptype(t, tag), price="", description=d,
                         detail_text="", scraped_at=TS))
write("darglobal.jsonl", projects)
counts = Counter(r["country"] for r in projects)

DG = [
doc("darglobal","About DarGlobal",B+"/",
"DarGlobal is a London-listed international luxury real estate developer, investor and asset manager. It creates high-quality communities, landmark destinations and lifestyle-driven assets in the UAE, Saudi Arabia, Qatar, Oman, Spain and London, spanning premium hospitality, commercial, entertainment and exclusive golf communities. It owns, invests in, develops and operates high-end real estate, combining global partnerships, strong fundamentals and disciplined execution. The group is listed on the London Stock Exchange."),
doc("darglobal","DarGlobal key figures",B+"/",
"Key figures shown on the DarGlobal home page (indicative, aligned with disclosures as of Q3 2026): 32 years of track record, about $23 billion gross development value (GDV), 7 international markets and 12+ global brand partners."),
doc("darglobal","DarGlobal business lines",B+"/",
"DarGlobal's activities: (1) Building luxury communities - fully integrated, masterplanned communities and exclusive residential enclaves (see /luxury-golf-communities). (2) Hospitality & leisure - hospitality-led assets developed and operated with global brands (see /hospitality). (3) Private membership - a new generation of private members clubs, including one planned in Jeddah, Saudi Arabia (see /exclusive-membership). (4) Golf - golf is a cornerstone of the community strategy, anchoring premium developments. (5) Commercial - high-quality commercial assets for recurring income (see /commercial). (6) Asset management - Dar Global Capital Partners (DGCP), the DFSA-regulated investment management subsidiary headquartered in the Dubai International Financial Centre (DIFC), deploying capital in equity, debt and hybrid instruments across GCC, European and US gateway markets (see /investor). (7) Tokenization - real estate tokenization and digital ownership structures to improve liquidity and access (see /tokenization)."),
doc("darglobal","DarGlobal brand partners and collaborations",B+"/",
"DarGlobal collaborates with luxury and lifestyle brands on branded residences and interiors. Partner pages exist for: Aston Martin, Elie Saab, FENDI Casa, Automobili Lamborghini, Marriott (Marriott Residences AIDA Oman), Missoni, Mouawad, Pagani, The Trump Organization, W Hotels (W Residences) and Paramount. Example projects: The Astera with interiors by Aston Martin (Al Marjan Island, RAK), Da Vinci Tower with interiors by Pagani (Dubai), Urban Oasis by Missoni (Dubai), Les Vagues by Elie Saab (Doha), Neptune with interiors by Mouawad (Riyadh), Azure Oceanfront Villas with interiors by Fendi Casa (AIDA, Oman)."),
doc("darglobal","DarGlobal projects page: filters and coverage",B+"/projects",
"The DarGlobal projects page (/projects) lists %d projects and can be filtered by Type (Apartments, Villas, Hotel Rooms) and by Location (United Arab Emirates, Spain, Qatar, Oman, United Kingdom, Saudi Arabia). Visitors can register their interest with full name, phone, email, a project selection and how they heard about DarGlobal. Project counts in this dataset by country: United Arab Emirates %d, Spain %d, Qatar %d, Oman %d, United Kingdom %d, Saudi Arabia %d."
 % (len(projects), counts["United Arab Emirates (UAE)"], counts["Spain"], counts["Qatar"], counts["Oman"], counts["United Kingdom"], counts["Saudi Arabia (KSA)"])),
doc("darglobal","Why invest with DarGlobal",B+"/why-invest",
"DarGlobal presents itself as a premier international luxury real estate investment and development platform focused on architecturally distinctive, design-led residences in sought-after destinations. It positions its portfolio (masterplanned communities, branded luxury apartments, and hospitality-led destinations built with partners from automotive, fashion and hospitality) for investors seeking rental income, long-term capital appreciation or geographic diversification."),
doc("darglobal","Press: new Jeddah development (16 Nov 2026)",B+"/press/dar-global-expands-saudi-arabia-portfolio-with-new-jeddah-development-valued-at-sar-1-billion",
"16 Nov 2026 - Dar Global announced plans for a new mixed-use development in Jeddah, Saudi Arabia, valued at SAR 1 billion, expanding its Saudi Arabia portfolio.","Saudi Arabia (KSA)"),
doc("darglobal","Press: DGCP targets Dubai opportunities (26 Oct 2026)",B+"/press/dar-global-capital-partners-targets-high-value-real-estate-opportunities-dubai",
"26 Oct 2026 - Dar Global Capital Partners (DGCP), the alternative asset management arm of Dar Global, announced a strategic focus on deploying capital into high-value real estate opportunities in Dubai as part of its global investment mandate.","United Arab Emirates (UAE)"),
doc("darglobal","Press: Trump Villas Simaisma sales open (7 Oct 2026)",B+"/press/dar-global-opens-sales-trump-villas-simaisma-qatar-unprecedented-interest",
"7 Oct 2026 - Dar Global opened sales for its Trump Villas within Trump International Golf Club Simaisma, Qatar, reporting very strong interest.","Qatar"),
doc("darglobal","Press: HY 2026 results (30 Sep 2026)",B+"/press/dar-global-delivers-66-percent-revenue-growth-hy-2026-portfolio-gdv-reaches-23-billion",
"30 Sep 2026 - Dar Global reported unaudited interim results for the six months ended 30 June 2026 (HY 2026): 66% revenue growth, with portfolio gross development value reaching $23 billion."),
doc("darglobal","Press: Gulf Asia Contracting for Trump Tower Dubai (6 Aug 2026)",B+"/press/dar-global-appoints-gulf-asia-contracting-for-trump-international-hotel-tower-dubai",
"6 Aug 2026 - Dar Global awarded the construction contract for the podium of Trump International Hotel & Tower, Dubai, to Gulf Asia Contracting.","United Arab Emirates (UAE)"),
doc("darglobal","Press: Azure Oceanfront Villas with Fendi Casa (29 Jun 2026)",B+"/press/darglobal-fendi-casa-announce-azure-oceanfront-villas-oman",
"29 Jun 2026 - Dar Global and FENDI Casa announced Azure Oceanfront Villas, a collection of ultra-luxury mansions with interiors by FENDI Casa, set within the AIDA cliffs development in Oman.","Oman"),
]
write("darglobal_info.jsonl", DG)

W = "https://wasalt.sa/en/"
KSA = "Saudi Arabia (KSA)"
WS = [
doc("wasalt","About Wasalt",W,
"Wasalt (wasalt.sa) is described on its site as the first AI-powered real estate platform in Saudi Arabia, covering residential and commercial properties for sale and rent. Every listing is said to be verified by REGA (the Real Estate General Authority). It is a joint venture between Dar Al Arkan and Quara Holding. Main navigation: Buy, Rent, Projects and Daily Rentals (new).",KSA),
doc("wasalt","Wasalt features: AI, matchmaker, communities, auctions",W,
"Wasalt features: (1) AI - a partnership with propgenius.ai to predict property prices from market trends and estimate return on investment for properties for sale (some pages show a predicted 5-year ROI). (2) Matchmaker - a questionnaire about your requirements, after which a real estate broker is assigned to contact you. (3) Communities - explore communities and view plots with prices, and book a plot online. (4) Auctions - a partnership with the Entrustment and Liquidation Centre (Infath) for listing and joining property auctions. (5) Interactive maps for navigating districts and cities. (6) Loan partners offering home loans. Wasalt has a website and iOS and Android apps.",KSA),
doc("wasalt","Wasalt property types and search filters",W,
"Property types on Wasalt - residential for sale: houses, villas, apartments/flats, plots/land; residential for rent: apartments and villas; commercial for sale: shops, office space, plots; commercial for rent: shops and office space. Other category pages include buildings, rest houses and lands. Search filters include property type, number of rooms/bedrooms, budget/price range, furnished or unfurnished, and location (city and district). Results can be sorted (default: relevance).",KSA),
doc("wasalt","Wasalt website structure and URL patterns",W,
"Wasalt category (search results) pages follow patterns such as /en/properties-for-sale-in-riyadh, /en/apartments-for-sale-in-riyadh, /en/villas-for-sale-in-jeddah, /en/lands-for-sale-in-makkah-<district> and /en/buildings-for-sale-in-saudi-arabia, with numbered pagination via ?page=N. Individual property pages use /en/property/<country>/<type>-<area>-sqm-with-<n>-bedrooms-<id>, for example 'Apartment 219 SQM with 6 Bedrooms, Tuwaiq, West Riyadh, Riyadh'. Cities covered include Riyadh, Jeddah, Makkah, Madinah, Dammam, Khobar, Buraidah and Taif.",KSA),
doc("wasalt","Wasalt listing volumes (snapshot, Nov 2026)",W+"properties-for-sale-in-riyadh",
"Result counts shown on Wasalt category pages when this dataset was collected (they change constantly): Properties for sale in Riyadh about 4,056; Apartments for sale in Riyadh about 7,818 (236 pages); Properties for sale in North Riyadh about 2,475 (69 pages); Apartments for sale in South Riyadh about 645 (20 pages); Buildings for sale in Saudi Arabia about 628 (20 pages); Apartments for rent in Riyadh under SAR 45,000 about 466.",KSA),
doc("wasalt","Wasalt price guidance for Riyadh (from Wasalt guide pages)",W+"apartments-for-sale-in-south-riyadh",
"Indicative price guidance written in Wasalt's own guide text (not live listings): apartments for sale in Riyadh typically range from about SAR 300,000 to SAR 1,000,000 depending on location and amenities. In South Riyadh apartments are about SAR 300,000-600,000 (studios from about SAR 200,000; 2-bedroom units about SAR 300,000-450,000). In North Riyadh apartments are about SAR 500,000-1.2 million and villas about SAR 1.5 million to over SAR 5 million.",KSA),
doc("wasalt","Wasalt contact and support",W,
"Wasalt support phone number listed on its home page: 8001233227 (Saudi Arabia). Users can also leave a contact phone number to be called back, and the Matchmaker feature assigns a broker. Wasalt's own site is wasalt.sa (also wasalt.com).",KSA),
doc("wasalt","Relationship between DarGlobal and Wasalt",W,
"Wasalt is a joint venture of Dar Al Arkan and Quara Holding. DarGlobal (Dar Global) is the London-listed international luxury developer associated with Dar Al Arkan. They are separate businesses: DarGlobal develops and sells luxury branded projects, while Wasalt is a property marketplace with verified listings in Saudi Arabia.",KSA),
]
write("wasalt_info.jsonl", WS)
print(dict(counts))
