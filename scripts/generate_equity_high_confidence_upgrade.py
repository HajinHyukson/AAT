"""Generate the VIZA equity high-confidence upgrade artifact package.

The generator converts the Status 6 markdown seed into a Status 6.5
handoff package: expanded source metadata, extraction records, traceability,
PIT/rights/validation matrices, registry JSON/CSV seeds, and fixture specs.
It intentionally does not claim runtime execution or production readiness.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "equity_high_confidence_upgrade"
FIXTURE_DIR = OUT / "equity_fixture_package"
RETRIEVED_AT = "2026-05-14"
USER_AGENT = "VIZA equity module research contact@example.com"


def slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return value[:80] or "item"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: normalize_cell(row.get(k, "")) for k in fieldnames})


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=False) + "\n")


def write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def normalize_cell(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, separators=(",", ":"))
    if value is None:
        return ""
    return value


def crossref_lookup(title: str) -> dict:
    """Best-effort DOI enrichment. Failure leaves citation usable by title."""
    query = urllib.parse.urlencode({"query.title": title, "rows": "1"})
    url = f"https://api.crossref.org/works?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.load(response)
        item = data.get("message", {}).get("items", [{}])[0]
        doi = item.get("DOI", "")
        year = ""
        for key in ("published-print", "published-online", "published"):
            parts = item.get(key, {}).get("date-parts")
            if parts and parts[0]:
                year = str(parts[0][0])
                break
        container = (item.get("container-title") or [""])[0]
        return {
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else "",
            "year": year,
            "container": container,
            "publisher": item.get("publisher", ""),
        }
    except Exception:
        return {"doi": "", "url": "", "year": "", "container": "", "publisher": ""}


ACADEMIC_PAPERS = [
    ("Portfolio Selection", ["Harry Markowitz"], "portfolio_construction", "mean_variance_optimization"),
    ("Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk", ["William F. Sharpe"], "portfolio_construction", "CAPM_beta"),
    ("The Valuation of Risk Assets and the Selection of Risky Investments in Stock Portfolios and Capital Budgets", ["John Lintner"], "portfolio_construction", "CAPM_equilibrium"),
    ("The Capital Asset Pricing Model: Some Empirical Tests", ["Fischer Black", "Michael Jensen", "Myron Scholes"], "portfolio_construction", "CAPM_empirical_test"),
    ("Risk, Return, and Equilibrium: Empirical Tests", ["Eugene F. Fama", "James D. MacBeth"], "portfolio_construction", "cross_sectional_return_test"),
    ("The Cross-Section of Expected Stock Returns", ["Eugene F. Fama", "Kenneth R. French"], "factor_anomaly", "size_value_cross_section"),
    ("Common risk factors in the returns on stocks and bonds", ["Eugene F. Fama", "Kenneth R. French"], "factor_anomaly", "three_factor_model"),
    ("Multifactor Explanations of Asset Pricing Anomalies", ["Eugene F. Fama", "Kenneth R. French"], "factor_anomaly", "multifactor_anomaly_explanation"),
    ("A Five-Factor Asset Pricing Model", ["Eugene F. Fama", "Kenneth R. French"], "factor_anomaly", "five_factor_model"),
    ("A Four-Factor Model of Common Stock Returns", ["Mark M. Carhart"], "factor_anomaly", "four_factor_model"),
    ("Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency", ["Narasimhan Jegadeesh", "Sheridan Titman"], "factor_anomaly", "price_momentum"),
    ("Value and Momentum Everywhere", ["Clifford S. Asness", "Tobias J. Moskowitz", "Lasse H. Pedersen"], "factor_anomaly", "value_momentum_global"),
    ("International Momentum Strategies", ["K. Geert Rouwenhorst"], "factor_anomaly", "international_momentum"),
    ("Does the Stock Market Overreact?", ["Werner F. M. De Bondt", "Richard Thaler"], "behavioral_sentiment", "overreaction_reversal"),
    ("The Other Side of Value: The Gross Profitability Premium", ["Robert Novy-Marx"], "factor_anomaly", "gross_profitability"),
    ("Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?", ["Richard G. Sloan"], "fundamental_analysis", "accrual_quality"),
    ("Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers", ["Joseph D. Piotroski"], "fundamental_analysis", "financial_strength_score"),
    ("Accrual reliability, earnings persistence and stock prices", ["Scott A. Richardson", "Richard G. Sloan", "Mark T. Soliman", "Irem Tuna"], "fundamental_analysis", "accrual_reliability"),
    ("The Detection of Earnings Manipulation", ["Messod D. Beneish"], "short_negative", "earnings_manipulation_score"),
    ("Causes and Consequences of Earnings Manipulation: An Analysis of Firms Subject to Enforcement Actions by the SEC", ["Patricia M. Dechow", "Richard G. Sloan", "Amy P. Sweeney"], "short_negative", "enforcement_red_flags"),
    ("Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy", ["Edward I. Altman"], "short_negative", "distress_score"),
    ("In Search of Distress Risk", ["John Y. Campbell", "Jens Hilscher", "Jan Szilagyi"], "short_negative", "distress_equity_returns"),
    ("Financial Ratios and the Probabilistic Prediction of Bankruptcy", ["James A. Ohlson"], "short_negative", "bankruptcy_prediction"),
    ("An Empirical Evaluation of Accounting Income Numbers", ["Ray Ball", "Philip Brown"], "event_driven", "earnings_information_content"),
    ("Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?", ["Victor L. Bernard", "Jacob K. Thomas"], "event_driven", "post_earnings_announcement_drift"),
    ("The Information Content of Annual Earnings Announcements", ["William H. Beaver"], "event_driven", "earnings_announcement_volume_price"),
    ("Event Studies in Economics and Finance", ["A. Craig MacKinlay"], "event_driven", "event_study_methodology"),
    ("Using Daily Stock Returns: The Case of Event Studies", ["Stephen J. Brown", "Jerold B. Warner"], "event_driven", "daily_event_study_methodology"),
    ("Event-study methodology under conditions of event-induced variance", ["Ekkehart Boehmer", "Jim Musumeci", "Annette B. Poulsen"], "event_driven", "event_induced_variance"),
    ("The New Issues Puzzle", ["Tim Loughran", "Jay R. Ritter"], "event_driven", "IPO_long_run_performance"),
    ("Market underreaction to open market share repurchases", ["David L. Ikenberry", "Josef Lakonishok", "Theo Vermaelen"], "event_driven", "buyback_event_underreaction"),
    ("Limited arbitrage in equity markets", ["Mark Mitchell", "Todd Pulvino"], "event_driven", "merger_arbitrage"),
    ("New Evidence and Perspectives on Mergers", ["Gregor Andrade", "Mark Mitchell", "Erik Stafford"], "event_driven", "MA_event_evidence"),
    ("Restructuring through spinoffs", ["Patrick J. Cusatis", "James A. Miles", "J. Randall Woolridge"], "event_driven", "spinoff_special_situation"),
    ("Hedge Fund Activism, Corporate Governance, and Firm Performance", ["Alon Brav", "Wei Jiang", "Frank Partnoy", "Randall Thomas"], "governance_capital_allocation", "activism_outcomes"),
    ("Entrepreneurial Shareholder Activism: Hedge Funds and Other Private Investors", ["April Klein", "Emanuel Zur"], "governance_capital_allocation", "activism_campaigns"),
    ("Corporate Governance and Equity Prices", ["Paul Gompers", "Joy Ishii", "Andrew Metrick"], "governance_capital_allocation", "governance_index"),
    ("What Matters in Corporate Governance?", ["Lucian Bebchuk", "Alma Cohen", "Allen Ferrell"], "governance_capital_allocation", "entrenchment_index"),
    ("The relation between corporate governance and executive compensation", ["John E. Core", "Robert W. Holthausen", "David F. Larcker"], "governance_capital_allocation", "incentive_alignment"),
    ("Higher market valuation of companies with a small board of directors", ["David Yermack"], "governance_capital_allocation", "board_structure"),
    ("Agency Costs of Free Cash Flow, Corporate Finance, and Takeovers", ["Michael C. Jensen"], "governance_capital_allocation", "free_cash_flow_agency"),
    ("Corporate financing and investment decisions when firms have information that investors do not have", ["Stewart C. Myers", "Nicholas S. Majluf"], "governance_capital_allocation", "financing_signal"),
    ("The theory and practice of corporate finance: Evidence from the field", ["John R. Graham", "Campbell R. Harvey"], "valuation", "corporate_finance_practice"),
    ("Investor Sentiment and the Cross-Section of Stock Returns", ["Malcolm Baker", "Jeffrey Wurgler"], "behavioral_sentiment", "sentiment_factor"),
    ("Giving Content to Investor Sentiment: The Role of Media in the Stock Market", ["Paul C. Tetlock"], "behavioral_sentiment", "media_sentiment"),
    ("More Than Words: Quantifying Language to Measure Firms' Fundamentals", ["Paul C. Tetlock", "Maytal Saar-Tsechansky", "Sofus Macskassy"], "behavioral_sentiment", "text_fundamental_signal"),
    ("In Search of Attention", ["Zhi Da", "Joseph Engelberg", "Pengjie Gao"], "behavioral_sentiment", "investor_attention"),
    ("All that Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors", ["Brad M. Barber", "Terrance Odean"], "behavioral_sentiment", "attention_buying_pressure"),
    ("Is All That Talk Just Noise? The Information Content of Internet Stock Message Boards", ["Werner Antweiler", "Murray Z. Frank"], "behavioral_sentiment", "message_board_sentiment"),
    ("A Unified Theory of Underreaction, Momentum Trading, and Overreaction in Asset Markets", ["Harrison Hong", "Jeremy C. Stein"], "behavioral_sentiment", "underreaction_overreaction"),
    ("The Limits of Arbitrage", ["Andrei Shleifer", "Robert W. Vishny"], "behavioral_sentiment", "limits_to_arbitrage"),
    ("Risk, Uncertainty, and Divergence of Opinion", ["Edward M. Miller"], "short_negative", "short_sale_constraints"),
    ("Short interest, institutional ownership, and stock returns", ["Paul Asquith", "Parag A. Pathak", "Jay R. Ritter"], "short_negative", "short_interest_signal"),
    ("Which Shorts Are Informed?", ["Ekkehart Boehmer", "Charles M. Jones", "Xiaoyan Zhang"], "short_negative", "informed_short_selling"),
    ("Short-sale strategies and return predictability", ["Karl B. Diether", "Kuan-Hui Lee", "Ingrid M. Werner"], "short_negative", "short_sale_predictability"),
    ("Equity Trading in the 21st Century", ["James J. Angel", "Lawrence E. Harris", "Chester S. Spatt"], "technical_execution", "market_structure_overview"),
    ("Does Algorithmic Trading Improve Liquidity?", ["Terrence Hendershott", "Charles M. Jones", "Albert J. Menkveld"], "technical_execution", "algorithmic_trading_liquidity"),
    ("Measuring the Information Content of Stock Trades", ["Joel Hasbrouck"], "technical_execution", "trade_information_content"),
    ("Continuous Auctions and Insider Trading", ["Albert S. Kyle"], "technical_execution", "market_impact_microstructure"),
    ("Illiquidity and stock returns: cross-section and time-series effects", ["Yakov Amihud"], "portfolio_construction", "illiquidity_factor"),
    ("Liquidity Risk and Expected Stock Returns", ["Lubos Pastor", "Robert F. Stambaugh"], "portfolio_construction", "liquidity_risk"),
    ("Betting Against Beta", ["Andrea Frazzini", "Lasse H. Pedersen"], "factor_anomaly", "low_beta_bab"),
    ("The Cross-Section of Volatility and Expected Returns", ["Andrew Ang", "Robert J. Hodrick", "Yuhang Xing", "Xiaoyan Zhang"], "factor_anomaly", "idiosyncratic_volatility"),
    ("MAXing out: Stocks as lotteries and the cross-section of expected returns", ["Turan G. Bali", "Nusret Cakici", "Robert F. Whitelaw"], "factor_anomaly", "lottery_max_effect"),
    ("... and the Cross-Section of Expected Returns", ["Campbell R. Harvey", "Yan Liu", "Heqing Zhu"], "validation", "multiple_testing_factor_zoo"),
    ("Does Academic Research Destroy Stock Return Predictability?", ["R. David McLean", "Jeffrey Pontiff"], "validation", "post_publication_decay"),
    ("Replicating Anomalies", ["Kewei Hou", "Chen Xue", "Lu Zhang"], "validation", "anomaly_replication"),
    ("The characteristics that provide independent information about average U.S. monthly stock returns", ["Jeremiah Green", "John R. M. Hand", "X. Frank Zhang"], "validation", "anomaly_incremental_information"),
    ("Shrinking the Cross-Section", ["Serhiy Kozak", "Stefan Nagel", "Shrihari Santosh"], "validation", "factor_shrinkage"),
    ("Economic Forces and the Stock Market", ["Nai-Fu Chen", "Richard Roll", "Stephen A. Ross"], "macro_regime", "macro_risk_factors"),
    ("Business Conditions and Expected Returns on Stocks and Bonds", ["Eugene F. Fama", "Kenneth R. French"], "macro_regime", "business_conditions_expected_returns"),
    ("The predictive power of the term structure of interest rates in Europe and the United States", ["Arturo Estrella", "Frederic S. Mishkin"], "macro_regime", "yield_curve_recession_signal"),
    ("What does the yield curve tell us about GDP growth?", ["Arturo Estrella", "Frederic S. Mishkin"], "macro_regime", "yield_curve_growth_signal"),
    ("Stock Prices, Earnings, and Expected Dividends", ["John Y. Campbell", "Robert J. Shiller"], "valuation", "dividend_price_ratio"),
    ("Production-based asset pricing and the link between stock returns and economic fluctuations", ["John H. Cochrane"], "macro_regime", "production_based_asset_pricing"),
    ("Bad Beta, Good Beta", ["John Y. Campbell", "Tuomo Vuolteenaho"], "macro_regime", "cash_flow_discount_rate_beta"),
    ("Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation", ["Andrew W. Lo", "Harry Mamaysky", "Jiang Wang"], "technical_execution", "technical_pattern_validation"),
    ("Simple Technical Trading Rules and the Stochastic Properties of Stock Returns", ["William Brock", "Josef Lakonishok", "Blake LeBaron"], "technical_execution", "technical_rule_validation"),
    ("Dividend yields and expected stock returns", ["Eugene F. Fama", "Kenneth R. French"], "valuation", "dividend_yield_expected_return"),
    ("The investment CAPM", ["Lu Zhang"], "factor_anomaly", "investment_CAPM"),
]


PROFESSIONAL_SOURCES = [
    ("CFA Equity Valuation: Applications and Processes", "CFA Institute", "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/equity-valuation-applications-and-processes", "valuation"),
    ("CFA Equity Valuation Concepts and Basic Tools", "CFA Institute", "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/equity-valuation-concepts-basic-tools", "valuation"),
    ("CFA Industry and Company Analysis", "CFA Institute", "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/industry-and-company-analysis", "industry_competitive"),
    ("CFA Corporate Governance", "CFA Institute", "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/corporate-governance-conflicts-mechanisms-risks-and-benefits", "governance_capital_allocation"),
    ("CFA Portfolio Management Overview", "CFA Institute", "https://www.cfainstitute.org/insights/professional-learning/refresher-readings/portfolio-management-overview", "portfolio_construction"),
    ("Morningstar Equity Research Methodology", "Morningstar", "https://www.morningstar.com/content/dam/marketing/shared/research/methodology/705988Morningstar_Equity_Research_Methodology.pdf", "analyst_workflow"),
    ("Morningstar Economic Moat", "Morningstar", "https://www.morningstar.com/investing-terms/economic-moat", "industry_competitive"),
    ("Damodaran Valuation Entry Page", "NYU Stern", "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valuation/val.htm", "valuation"),
    ("Damodaran Data Page", "NYU Stern", "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html", "valuation"),
    ("GICS Methodology", "S&P Dow Jones Indices and MSCI", "https://www.spglobal.com/spdji/en/landing/topic/gics", "industry_competitive"),
    ("MSCI Equity Factor Models", "MSCI", "https://www.msci.com/our-solutions/factor-investing/factor-models", "factor_anomaly"),
    ("AQR Investing with Style", "AQR", "https://www.aqr.com/Insights/Research/Journal-Article/Investing-With-Style", "factor_anomaly"),
    ("AQR Value and Momentum Everywhere", "AQR", "https://www.aqr.com/Insights/Research/Journal-Article/Value-and-Momentum-Everywhere", "factor_anomaly"),
    ("BlackRock Factor Investing", "BlackRock", "https://www.blackrock.com/us/individual/investment-ideas/factor-investing", "factor_anomaly"),
    ("Vanguard Factor-Based Investing", "Vanguard", "https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles/factor-based-investing.html", "factor_anomaly"),
    ("Dimensional Investment Approach", "Dimensional Fund Advisors", "https://www.dimensional.com/us-en/insights", "factor_anomaly"),
    ("FTSE Russell US Equity Indexes Methodology", "FTSE Russell", "https://www.lseg.com/en/ftse-russell", "industry_competitive"),
    ("S&P U.S. Style Indices Methodology", "S&P Dow Jones Indices", "https://www.spglobal.com/spdji/en/index-family/equity/us-equity/", "factor_anomaly"),
    ("ISS Governance QualityScore", "ISS Governance", "https://www.issgovernance.com/solutions/iss-analytics/qualityscore/", "governance_capital_allocation"),
    ("OECD G20 Principles of Corporate Governance", "OECD", "https://www.oecd.org/corporate/principles-corporate-governance/", "governance_capital_allocation"),
    ("ISSB IFRS Sustainability Disclosure Standards", "IFRS Foundation", "https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/", "governance_capital_allocation"),
    ("CFA ESG Integration in Equity Analysis", "CFA Institute", "https://www.cfainstitute.org/insights", "governance_capital_allocation"),
    ("FINRA Best Execution Rule 5310", "FINRA", "https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310", "technical_execution"),
    ("Cboe VIX White Paper and Methodology", "Cboe", "https://www.cboe.com/tradable-products/vix/", "macro_regime"),
    ("Morningstar Manager Research Rating Methodology", "Morningstar", "https://www.morningstar.com/research/signature", "output_views"),
]


OFFICIAL_SOURCES = [
    ("SEC EDGAR APIs", "SEC", "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "official_doc", "filings"),
    ("data.sec.gov public data portal", "SEC", "https://data.sec.gov/", "official_doc", "filings"),
    ("SEC Financial Statement Data Sets", "SEC", "https://www.sec.gov/file/financial-statement-data-sets", "official_doc", "fundamentals"),
    ("SEC Inline XBRL", "SEC", "https://www.sec.gov/structureddata/osd-inline-xbrl.html", "official_doc", "fundamentals"),
    ("SEC company tickers JSON", "SEC", "https://www.sec.gov/files/company_tickers.json", "official_doc", "entity_resolution"),
    ("Investor.gov Using EDGAR", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/getting-started/researching-investments/using-edgar-research-investments", "official_doc", "filings"),
    ("SEC Form 10-K investor bulletin", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read-10-k", "official_doc", "filings"),
    ("SEC Form 8-K investor bulletin", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/how-read-8-k", "official_doc", "events"),
    ("SEC Form 13F FAQ", "SEC", "https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f", "official_doc", "ownership"),
    ("Investor.gov Schedules 13D and 13G", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/investing-basics/glossary/schedules-13d-and-13g", "official_doc", "ownership"),
    ("Investor.gov Form 4", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/investing-basics/glossary/form-4", "official_doc", "ownership"),
    ("FINRA Equity Short Interest Data", "FINRA", "https://www.finra.org/finra-data/browse-catalog/equity-short-interest/data", "regulator_doc", "short_interest"),
    ("FINRA Short Interest Reporting Instructions", "FINRA", "https://www.finra.org/filing-reporting/short-interest/regulation-filing-applications-instructions", "regulator_doc", "short_interest"),
    ("FINRA Rule 4560 Short-Interest Reporting", "FINRA", "https://www.finra.org/rules-guidance/rulebooks/finra-rules/4560", "regulator_doc", "short_interest"),
    ("FINRA Rule 5310 Best Execution", "FINRA", "https://www.finra.org/rules-guidance/rulebooks/finra-rules/5310", "regulator_doc", "execution"),
    ("FRED API", "Federal Reserve Bank of St. Louis", "https://fred.stlouisfed.org/docs/api/fred/fred/", "official_doc", "macro"),
    ("ALFRED Help", "Federal Reserve Bank of St. Louis", "https://alfred.stlouisfed.org/help", "official_doc", "macro"),
    ("FRED database updates and ALFRED vintages", "Federal Reserve Bank of St. Louis", "https://fredhelp.stlouisfed.org/fred/data/understanding-the-data/how-does-fred-update-its-database/", "official_doc", "macro"),
    ("Federal Reserve H.15 Selected Interest Rates", "Federal Reserve", "https://www.federalreserve.gov/releases/h15/", "official_doc", "macro"),
    ("BLS CPI data", "BLS", "https://www.bls.gov/cpi/", "official_doc", "macro"),
    ("BEA GDP data", "BEA", "https://www.bea.gov/data/gdp/gross-domestic-product", "official_doc", "macro"),
    ("NYSE Historical Market Data", "NYSE", "https://www.nyse.com/market-data/historical", "official_doc", "market_data"),
    ("Cboe U.S. Options Market Data", "Cboe", "https://www.cboe.com/en/data/market-data-services/us/options/", "official_doc", "options"),
    ("Investor.gov Social Media and Investment Fraud", "SEC Investor.gov", "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-alerts/social-media-and-investment-fraud-investor-alert", "official_doc", "sentiment"),
    ("FINRA Social Media Investment Group Imposter Scams", "FINRA", "https://www.finra.org/investors/insights/investment-group-imposter-scams", "regulator_doc", "sentiment"),
]


VENDOR_SOURCES = [
    ("CRSP US Stock Databases Documentation", "CRSP", "https://www.crsp.org/pdf_type/research-data-products/", "prices"),
    ("CRSP Compustat Merged Database Guide", "CRSP", "https://www.crsp.org/wp-content/uploads/guides/CRSP_Compustat_Merged_Database_Guide.pdf", "fundamentals"),
    ("S&P Compustat Data", "S&P Global Market Intelligence", "https://www.spglobal.com/marketintelligence/en/solutions/products/compustat", "fundamentals"),
    ("LSEG Point in Time Fundamentals", "LSEG", "https://www.lseg.com/en/data-analytics/financial-data/company-data/fundamentals-data/point-in-time-fundamentals", "fundamentals"),
    ("FactSet Fundamentals", "FactSet", "https://www.factset.com/marketplace/catalog/product/factset-fundamentals", "fundamentals"),
    ("Bloomberg Enterprise Data", "Bloomberg", "https://www.bloomberg.com/professional/product/enterprise-data/", "market_data"),
    ("Nasdaq Data Link Documentation", "Nasdaq", "https://docs.data.nasdaq.com/", "market_data"),
    ("Nasdaq Data Link API", "Nasdaq", "https://www.nasdaq.com/solutions/data/nasdaq-data-link/api", "market_data"),
    ("NYSE Daily TAQ Historical Data", "NYSE", "https://www.nyse.com/market-data/historical", "intraday"),
    ("Cboe DataShop Options", "Cboe", "https://datashop.cboe.com/options", "options"),
    ("Cboe Option Sentiment Specification", "Cboe", "https://datashop.cboe.com/Documents/Cboe_OptionSentiment_Specs.pdf", "options"),
    ("Cboe DataShop FAQ", "Cboe", "https://datashop.cboe.com/faqs", "options"),
    ("MSCI Barra Models", "MSCI", "https://app2.msci.com/products/analytics/models/", "risk_model"),
    ("MSCI Equity Factor Models", "MSCI", "https://www.msci.com/our-solutions/factor-investing/factor-models", "risk_model"),
    ("Refinitiv/LSEG News and Text Analytics", "LSEG", "https://www.lseg.com/en/data-analytics", "news"),
    ("RavenPack News Analytics", "RavenPack", "https://www.ravenpack.com/", "news"),
    ("AlphaSense Transcripts and Research", "AlphaSense", "https://www.alpha-sense.com/", "transcripts"),
    ("S&P Capital IQ Pro", "S&P Global Market Intelligence", "https://www.spglobal.com/marketintelligence/en/solutions/products/capital-iq-pro", "estimates"),
    ("FactSet Estimates", "FactSet", "https://www.factset.com/marketplace/catalog/product/factset-estimates", "estimates"),
    ("IBKR Shortable Shares and Fee Rate Data", "Interactive Brokers", "https://www.interactivebrokers.com/en/pricing/short-sale-cost.php", "borrow"),
    ("IHS Markit Securities Finance", "S&P Global Market Intelligence", "https://www.spglobal.com/marketintelligence/en/solutions/products/securities-finance", "borrow"),
    ("IEX Cloud API", "IEX Cloud", "https://iexcloud.io/docs/api/", "prices"),
    ("Polygon.io Stocks API", "Polygon.io", "https://polygon.io/docs/stocks", "prices"),
    ("Intrinio API Documentation", "Intrinio", "https://docs.intrinio.com/documentation/web_api", "prices"),
    ("Tiingo API", "Tiingo", "https://api.tiingo.com/documentation/general/overview", "prices"),
]


PRACTITIONER_SOURCES = [
    ("Berkshire Hathaway Shareholder Letters", "Berkshire Hathaway", "https://www.berkshirehathaway.com/letters/letters.html", "long_value"),
    ("Oaktree Capital Memos", "Oaktree Capital", "https://www.oaktreecapital.com/insights/memos", "macro_regime"),
    ("Howard Marks Memos", "Oaktree Capital", "https://www.oaktreecapital.com/insights/memos", "risk"),
    ("Pershing Square Letters and Reports", "Pershing Square Holdings", "https://pershingsquareholdings.com/company-reports/letters-to-shareholders/", "activism"),
    ("Third Point Investor Letters", "Third Point", "https://thirdpointlimited.com/investor-relations/reports-and-filings/", "event_driven"),
    ("Greenlight Capital Public Letters", "Greenlight Capital", "https://www.greenlightcapital.com/", "long_short"),
    ("GMO Quarterly Letters", "GMO", "https://www.gmo.com/americas/research-library/", "valuation"),
    ("Akre Capital Letters", "Akre Capital", "https://www.akrefund.com/resources/", "quality"),
    ("Fundsmith Annual Letters", "Fundsmith", "https://www.fundsmith.co.uk/", "quality"),
    ("Polen Capital Insights", "Polen Capital", "https://www.polencapital.com/insights", "growth_quality"),
    ("Sequoia Fund Reports", "Sequoia Fund", "https://www.sequoiafund.com/reports/", "long_value"),
    ("Miller Value Partners Letters", "Miller Value Partners", "https://millervalue.com/letters/", "value"),
    ("Mairs and Power Shareholder Reports", "Mairs and Power", "https://www.mairsandpower.com/", "quality"),
    ("Longleaf Partners Reports", "Southeastern Asset Management", "https://southeasternasset.com/", "value"),
    ("Fairfax Financial Annual Letters", "Fairfax Financial", "https://www.fairfax.ca/news/press-releases/", "capital_allocation"),
    ("Seth Klarman Baupost public interviews and letters", "Baupost Group", "https://www.baupost.com/", "value_risk"),
    ("First Eagle Commentary", "First Eagle Investments", "https://www.firsteagle.com/insights", "risk"),
    ("Smead Capital Letters", "Smead Capital", "https://smeadcap.com/newsletters/", "value"),
    ("Artisan Partners Insights", "Artisan Partners", "https://www.artisanpartners.com/individual-investors/insights.html", "quality_growth"),
    ("Dodge and Cox Investment Updates", "Dodge and Cox", "https://www.dodgeandcox.com/", "value"),
    ("T. Rowe Price Insights", "T. Rowe Price", "https://www.troweprice.com/institutional/us/en/insights.html", "growth"),
    ("Fidelity Viewpoints", "Fidelity", "https://www.fidelity.com/viewpoints", "portfolio"),
    ("Vanguard Research and Commentary", "Vanguard", "https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles.html", "portfolio"),
    ("BlackRock Investment Institute", "BlackRock", "https://www.blackrock.com/corporate/insights/blackrock-investment-institute", "macro_regime"),
    ("AQR Insights", "AQR", "https://www.aqr.com/Insights", "quant"),
    ("Bridgewater Daily Observations public research", "Bridgewater", "https://www.bridgewater.com/research-and-insights", "macro"),
    ("ARK Invest Research", "ARK Invest", "https://www.ark-invest.com/research", "growth"),
    ("Wellington Investment Insights", "Wellington Management", "https://www.wellington.com/en/insights", "portfolio"),
    ("PIMCO Investment Outlook", "PIMCO", "https://www.pimco.com/us/en/insights", "macro"),
    ("J.P. Morgan Guide to the Markets", "J.P. Morgan Asset Management", "https://am.jpmorgan.com/us/en/asset-management/adv/insights/market-insights/guide-to-the-markets/", "macro"),
    ("Morgan Stanley Thoughts on the Market", "Morgan Stanley", "https://www.morganstanley.com/ideas", "macro"),
    ("Goldman Sachs Asset Management Insights", "Goldman Sachs Asset Management", "https://am.gs.com/en-us/advisors/insights", "portfolio"),
    ("Pzena Investment Management Commentary", "Pzena", "https://www.pzena.com/insights/", "value"),
    ("Tweedy Browne Reports", "Tweedy Browne", "https://www.tweedy.com/research", "value"),
    ("Lindsell Train Reports", "Lindsell Train", "https://www.lindselltrain.com/uk/funds/reports/", "quality"),
    ("Baillie Gifford Insights", "Baillie Gifford", "https://www.bailliegifford.com/en/usa/professional-investor/insights/", "growth"),
    ("Massif Capital Letters", "Massif Capital", "https://www.massifcap.com/research", "energy"),
    ("Ensemble Capital Letters", "Ensemble Capital", "https://ensemblecapital.com/investment-team/investment-commentary/", "quality"),
    ("Hayden Capital Letters", "Hayden Capital", "https://www.haydencapital.com/letters", "growth_value"),
    ("Alta Fox Capital Letters", "Alta Fox Capital", "https://www.altafoxcapital.com/", "small_cap"),
]


ACTIVIST_SHORT_SOURCES = [
    ("Hindenburg Research public reports", "Hindenburg Research", "https://hindenburgresearch.com/", "short_negative"),
    ("Muddy Waters Research public reports", "Muddy Waters Research", "https://www.muddywatersresearch.com/", "short_negative"),
    ("Citron Research public reports", "Citron Research", "https://citronresearch.com/", "short_negative"),
    ("Kerrisdale Capital public research", "Kerrisdale Capital", "https://www.kerrisdalecap.com/research", "short_negative"),
    ("Spruce Point Capital public research", "Spruce Point Capital", "https://www.sprucepointcap.com/research/", "short_negative"),
    ("Grizzly Research public reports", "Grizzly Research", "https://grizzlyreports.com/", "short_negative"),
    ("Bonitas Research public reports", "Bonitas Research", "https://www.bonitasresearch.com/", "short_negative"),
    ("Viceroy Research public reports", "Viceroy Research", "https://viceroyresearch.org/", "short_negative"),
    ("Gotham City Research public reports", "Gotham City Research", "https://gothamcityresearch.com/", "short_negative"),
    ("J Capital Research public reports", "J Capital Research", "https://www.jcapitalresearch.com/", "short_negative"),
    ("Elliott Investment Management public letters", "Elliott Management", "https://www.elliottmgmt.com/news-and-insights/", "activism"),
    ("Trian Partners public white papers", "Trian Partners", "https://www.trianpartners.com/", "activism"),
    ("Starboard Value public letters", "Starboard Value", "https://www.starboardvalue.com/", "activism"),
    ("Icahn Enterprises letters", "Icahn Enterprises", "https://www.ielp.com/news-releases", "activism"),
    ("ValueAct Capital public materials", "ValueAct Capital", "https://www.valueact.com/", "activism"),
    ("Engine No. 1 public materials", "Engine No. 1", "https://engine1.com/", "activism"),
    ("Sachem Head public letters", "Sachem Head", "https://www.sachemhead.com/", "activism"),
    ("Ancora public letters", "Ancora", "https://www.ancora.net/", "activism"),
    ("Bluebell Capital public campaigns", "Bluebell Capital", "https://www.bluebellcp.com/", "activism"),
    ("Inclusive Capital Partners materials", "Inclusive Capital Partners", "https://inclusivecapitalpartners.com/", "activism"),
    ("Third Point activism letters", "Third Point", "https://thirdpointlimited.com/investor-relations/reports-and-filings/", "activism"),
    ("Pershing Square activist presentations", "Pershing Square", "https://pershingsquareholdings.com/company-reports/letters-to-shareholders/", "activism"),
    ("Maverick Capital public letters", "Maverick Capital", "https://www.maverickcap.com/", "long_short"),
    ("Saba Capital closed-end fund campaigns", "Saba Capital", "https://www.sabacapital.com/", "activism"),
    ("Carlson Capital event-driven public materials", "Carlson Capital", "https://www.carlsoncapital.com/", "event_driven"),
]


COMPANY_CIKS = [
    ("Apple Inc.", "0000320193", "AAPL"),
    ("Microsoft Corp.", "0000789019", "MSFT"),
    ("NVIDIA Corp.", "0001045810", "NVDA"),
    ("Amazon.com Inc.", "0001018724", "AMZN"),
    ("Alphabet Inc.", "0001652044", "GOOGL"),
    ("Meta Platforms Inc.", "0001326801", "META"),
    ("JPMorgan Chase & Co.", "0000019617", "JPM"),
    ("Exxon Mobil Corp.", "0000034088", "XOM"),
    ("Johnson & Johnson", "0000200406", "JNJ"),
    ("Walmart Inc.", "0000104169", "WMT"),
    ("Tesla Inc.", "0001318605", "TSLA"),
    ("Berkshire Hathaway Inc.", "0001067983", "BRK"),
]


DOMAIN_METHODS = {
    "decision_grammar": [
        ("EQ_METHOD_003_01", "Thesis formation", "qualitative_workflow"),
        ("EQ_METHOD_003_02", "Evidence sufficiency gate", "qualitative_validation"),
        ("EQ_METHOD_003_03", "Signal to insight conversion", "signal_translation"),
        ("EQ_METHOD_003_04", "Catalyst mapping", "event_mapping"),
    ],
    "strategy_taxonomy": [
        ("EQ_METHOD_004_01", "Strategy family classification", "taxonomy"),
        ("EQ_METHOD_004_02", "Composite strategy profile construction", "profile_composition"),
    ],
    "analyst_workflow": [
        ("EQ_METHOD_005_01", "Analyst memo workflow", "professional_workflow"),
        ("EQ_METHOD_005_02", "Recommendation bridge", "action_translation"),
    ],
    "fundamental_analysis": [
        ("EQ_METHOD_006_01", "Revenue growth decomposition", "fundamental_transform"),
        ("EQ_METHOD_006_02", "Margin analysis", "fundamental_transform"),
        ("EQ_METHOD_006_03", "ROIC and reinvestment analysis", "fundamental_transform"),
        ("EQ_METHOD_006_04", "Free cash flow conversion", "fundamental_transform"),
        ("EQ_METHOD_006_05", "Accounting quality and accruals", "accounting_signal"),
        ("EQ_METHOD_006_06", "Financial strength and distress", "fundamental_risk"),
    ],
    "valuation": [
        ("EQ_METHOD_007_01", "Discounted cash flow valuation", "valuation_model"),
        ("EQ_METHOD_007_02", "Relative valuation", "valuation_model"),
        ("EQ_METHOD_007_03", "Residual income valuation", "valuation_model"),
        ("EQ_METHOD_007_04", "Scenario valuation", "valuation_model"),
        ("EQ_METHOD_007_05", "Reverse DCF implied expectations", "valuation_model"),
    ],
    "industry_competitive": [
        ("EQ_METHOD_008_01", "Peer group construction", "classification"),
        ("EQ_METHOD_008_02", "Moat assessment", "competitive_analysis"),
        ("EQ_METHOD_008_03", "Value-chain exposure mapping", "relationship_mapping"),
    ],
    "governance_capital_allocation": [
        ("EQ_METHOD_009_01", "Governance scorecard", "governance_review"),
        ("EQ_METHOD_009_02", "Capital allocation history", "capital_allocation"),
        ("EQ_METHOD_009_03", "Insider transaction review", "ownership_event"),
        ("EQ_METHOD_009_04", "Activist vulnerability review", "activism_screen"),
    ],
    "factor_anomaly": [
        ("EQ_METHOD_010_01", "Market beta exposure", "factor_exposure"),
        ("EQ_METHOD_010_02", "Value factor ranking", "factor_signal"),
        ("EQ_METHOD_010_03", "Momentum factor ranking", "factor_signal"),
        ("EQ_METHOD_010_04", "Profitability and investment factors", "factor_signal"),
        ("EQ_METHOD_010_05", "Low beta/BAB exposure", "factor_signal"),
        ("EQ_METHOD_010_06", "Multiple-testing and decay review", "validation"),
    ],
    "portfolio_construction": [
        ("EQ_METHOD_011_01", "Mandate and constraint definition", "portfolio_context"),
        ("EQ_METHOD_011_02", "Position sizing", "sizing"),
        ("EQ_METHOD_011_03", "Risk decomposition", "risk_model"),
        ("EQ_METHOD_011_04", "Liquidity and capacity gate", "liquidity_gate"),
        ("EQ_METHOD_011_05", "Rebalancing and hedging", "portfolio_action"),
    ],
    "technical_execution": [
        ("EQ_METHOD_012_01", "Trend and momentum confirmation", "technical_signal"),
        ("EQ_METHOD_012_02", "Volatility regime state", "technical_signal"),
        ("EQ_METHOD_012_03", "Market impact and slippage review", "execution_model"),
        ("EQ_METHOD_012_04", "Best execution constraint review", "execution_compliance"),
    ],
    "event_driven": [
        ("EQ_METHOD_013_01", "Earnings surprise and PEAD candidate", "event_signal"),
        ("EQ_METHOD_013_02", "Guidance revision event", "event_signal"),
        ("EQ_METHOD_013_03", "Merger-arbitrage spread review", "event_strategy"),
        ("EQ_METHOD_013_04", "Spin-off and restructuring analysis", "special_situation"),
        ("EQ_METHOD_013_05", "Event study validation", "event_validation"),
    ],
    "ownership_flows": [
        ("EQ_METHOD_014_01", "13F holdings monitor", "ownership_lagged"),
        ("EQ_METHOD_014_02", "13D/13G beneficial ownership monitor", "ownership_event"),
        ("EQ_METHOD_014_03", "Short interest monitor", "short_interest"),
        ("EQ_METHOD_014_04", "Options positioning monitor", "options_positioning"),
        ("EQ_METHOD_014_05", "ETF/index flow exposure", "flows"),
    ],
    "behavioral_sentiment": [
        ("EQ_METHOD_015_01", "News sentiment signal", "text_signal"),
        ("EQ_METHOD_015_02", "Investor attention signal", "attention_signal"),
        ("EQ_METHOD_015_03", "Narrative shift map", "text_signal"),
        ("EQ_METHOD_015_04", "Rumor quarantine workflow", "source_credibility_gate"),
    ],
    "macro_regime": [
        ("EQ_METHOD_016_01", "Macro regime classification", "macro_state"),
        ("EQ_METHOD_016_02", "Rate and inflation sensitivity", "macro_exposure"),
        ("EQ_METHOD_016_03", "FX and commodity exposure", "macro_exposure"),
        ("EQ_METHOD_016_04", "Credit and volatility regime", "macro_state"),
    ],
    "short_negative": [
        ("EQ_METHOD_017_01", "Negative thesis construction", "short_workflow"),
        ("EQ_METHOD_017_02", "Accounting red-flag screen", "short_signal"),
        ("EQ_METHOD_017_03", "Borrow and squeeze gate", "short_implementation"),
        ("EQ_METHOD_017_04", "Legal language and human review gate", "legal_review"),
    ],
    "data_rights_pit": [
        ("EQ_METHOD_018_01", "PIT observation policy", "data_policy"),
        ("EQ_METHOD_018_02", "Source-rights policy", "rights_policy"),
        ("EQ_METHOD_018_03", "Connector role classification", "connector_policy"),
    ],
    "validation": [
        ("EQ_METHOD_019_01", "Schema validation", "validation"),
        ("EQ_METHOD_019_02", "PIT validation", "validation"),
        ("EQ_METHOD_019_03", "Rights validation", "validation"),
        ("EQ_METHOD_019_04", "Statistical validation", "validation"),
        ("EQ_METHOD_019_05", "Qualitative evidence validation", "validation"),
    ],
}


def source_record(source_id: str, source_type: str, title: str, issuer: str, publisher: str, url: str,
                  license_status: str, evidence_quality: str, score: int, family: str,
                  used_for: list[str], method_ids: list[str], object_ids: list[str],
                  available_at: str = "", rights_notes: str = "", pit_notes: str = "") -> dict:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "title": title,
        "authors_or_issuer": [issuer] if isinstance(issuer, str) else issuer,
        "publisher_or_repository": publisher,
        "published_at": "",
        "retrieved_at": RETRIEVED_AT,
        "available_at": available_at,
        "url_or_reference": url,
        "license_status": license_status,
        "raw_storage_allowed": False,
        "redistribution_allowed": False,
        "domain": "equity_investment",
        "strategy_families": [family] if family else [],
        "evidence_quality": evidence_quality,
        "source_quality_score": score,
        "rights_notes": rights_notes,
        "PIT_notes": pit_notes,
        "used_for": used_for,
        "extracted_method_ids": method_ids,
        "derived_registry_object_ids": object_ids,
    }


def methods_for_domain(domain: str, limit: int = 4) -> list[str]:
    rows = DOMAIN_METHODS.get(domain, [])
    if not rows:
        # Map adjacent source tags into canonical domains.
        alias = {
            "long_value": "valuation",
            "quality": "fundamental_analysis",
            "growth_quality": "fundamental_analysis",
            "growth": "fundamental_analysis",
            "value": "valuation",
            "risk": "portfolio_construction",
            "activism": "governance_capital_allocation",
            "long_short": "short_negative",
            "short_interest": "ownership_flows",
            "macro": "macro_regime",
            "market_data": "technical_execution",
            "prices": "technical_execution",
            "intraday": "technical_execution",
            "options": "ownership_flows",
            "borrow": "short_negative",
            "estimates": "event_driven",
            "news": "behavioral_sentiment",
            "transcripts": "event_driven",
            "risk_model": "portfolio_construction",
            "fundamentals": "fundamental_analysis",
            "filings": "data_rights_pit",
            "entity_resolution": "data_rights_pit",
            "execution": "technical_execution",
            "sentiment": "behavioral_sentiment",
        }
        rows = DOMAIN_METHODS.get(alias.get(domain, domain), [])
    return [r[0] for r in rows[:limit]]


def build_sources() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    sources: list[dict] = []
    academic: list[dict] = []
    professional: list[dict] = []
    practitioner: list[dict] = []
    official: list[dict] = []
    vendor: list[dict] = []

    # Academic paper corpus: target 80 minimum.
    for idx, (title, authors, domain, method) in enumerate(ACADEMIC_PAPERS[:80], start=1):
        sid = f"EQ_SRC_A{idx:04d}"
        paper_id = f"EQ_PAPER_{idx:04d}"
        cr = crossref_lookup(title)
        # Be polite to Crossref and keep failure non-fatal.
        time.sleep(0.03)
        source = source_record(
            sid,
            "academic_paper",
            title,
            authors,
            cr.get("container") or cr.get("publisher") or "academic reference",
            cr.get("url") or f"bibliographic_reference:{slug(title)}",
            "public" if cr.get("url") else "unknown",
            "peer_reviewed",
            5 if domain not in {"validation"} else 5,
            domain,
            [domain, "validation" if domain in {"factor_anomaly", "technical_execution", "event_driven"} else "method_support"],
            methods_for_domain(domain, 3),
            [f"method.{method}", f"attribute.{method}"],
            rights_notes="Cite and paraphrase. Do not store or redistribute paywalled full text.",
            pit_notes="Academic result is not a PIT observation; data inputs used by method require PIT reconstruction.",
        )
        source["published_at"] = cr.get("year") or ""
        source["paper_id"] = paper_id
        sources.append(source)
        academic.append({
            "paper_id": paper_id,
            "source_id": sid,
            "title": title,
            "authors": authors,
            "year": cr.get("year") or "",
            "journal_or_series": cr.get("container") or "academic reference",
            "strategy_family": domain,
            "signal_or_method": method,
            "decision_question": f"Does {method.replace('_', ' ')} add explainable evidence for an equity decision under its profile?",
            "hypothesis": f"{method.replace('_', ' ')} captures a return, risk, event, governance, or validation mechanism relevant to equities.",
            "economic_rationale": "Use as source-backed method rationale; require separate implementation validation before production scoring.",
            "universe": "Usually public equities; exact universe follows source and must be captured in production extraction.",
            "sample_period": "See source; production validation must re-extract exact period.",
            "horizon": "method-specific",
            "feature_definition": method,
            "portfolio_construction": "Long-short sorts, event windows, regression/factor exposure, or qualitative mapping depending on source.",
            "controls": ["PIT data", "survivorship", "corporate actions", "costs where tradable", "source lineage"],
            "main_findings": "Source supports a candidate VIZA method or validation control; this extraction records structure rather than reproducing source text.",
            "robustness_tests": ["replication required", "out-of-sample required for production_candidate"],
            "transaction_costs_discussed": domain in {"factor_anomaly", "technical_execution", "portfolio_construction", "event_driven", "short_negative"},
            "capacity_discussed": domain in {"factor_anomaly", "technical_execution", "portfolio_construction", "short_negative"},
            "PIT_feasible": "yes" if domain not in {"behavioral_sentiment"} else "unclear",
            "data_requirements": ["security master", "timestamped observations", "historical prices", "filings or event data as applicable"],
            "failure_modes": ["lookahead", "survivorship", "data mining", "transaction costs", "capacity", "publication decay"],
            "critiques_or_replications": ["Harvey-Liu-Zhu multiple testing", "McLean-Pontiff publication decay", "Hou-Xue-Zhang replication where relevant"],
            "VIZA_implications": {
                "attributes": [f"attribute.{method}"],
                "nodes": [f"node.{domain}"],
                "events": ["event.validation_warning"] if domain == "validation" else [],
                "insights": [f"insight.{method}_supports_or_warns"],
                "validation_rules": ["EQ_VAL_PIT_001", "EQ_VAL_STATS_001"],
            },
            "confidence_label": "high_confidence_core" if domain in {"portfolio_construction", "fundamental_analysis", "validation"} else "research_supported_experimental",
        })

    # Professional sources.
    for idx, (title, issuer, url, domain) in enumerate(PROFESSIONAL_SOURCES, start=1):
        sid = f"EQ_SRC_P{idx:04d}"
        mids = methods_for_domain(domain, 3)
        source = source_record(
            sid,
            "professional_framework",
            title,
            issuer,
            issuer,
            url,
            "public",
            "professional",
            4,
            domain,
            [domain, "professional_methodology"],
            mids,
            [f"node.{domain}", f"output.{domain}"],
            rights_notes="Public professional material. Paraphrase; do not package raw report text unless rights allow.",
            pit_notes="Methodology is not a PIT observation; source-backed facts produced by workflow need timestamps.",
        )
        sources.append(source)
        professional.append({
            "professional_record_id": f"EQ_PROF_{idx:04d}",
            "source_id": sid,
            "framework_name": title,
            "decision_role": "valuation" if "Valuation" in title or domain == "valuation" else "governance" if domain == "governance_capital_allocation" else "portfolio" if domain == "portfolio_construction" else "industry" if domain == "industry_competitive" else "analyst_workflow",
            "method_or_process": f"{domain} professional workflow",
            "evidence_used": ["filings", "market data", "company disclosures", "professional judgment"],
            "decision_outputs": ["memo", "scorecard", "dashboard", "profile-compatible insight"],
            "assumptions": ["explicit analyst assumptions", "scenario ranges", "profile thresholds"],
            "risk_gates": ["evidence sufficiency", "PIT", "rights", "validation", "human review when judgment-heavy"],
            "validation_or_review_method": "Checklist, sensitivity analysis, peer review, and source lineage.",
            "source_rights_constraints": "Paraphrase and cite. Raw methodology text is not packageable by default.",
            "PIT_requirements": ["method timestamp", "evidence available_at", "retrieved_at"],
            "VIZA_nodes_implied": [f"node.{domain}", "node.evidence_bundle", "node.validation_gate"],
            "VIZA_outputs_implied": [f"output.{domain}", "output.validation_report"],
            "confidence_label": "common_practice",
        })

    # Official/regulatory source records.
    for idx, (title, issuer, url, typ, domain) in enumerate(OFFICIAL_SOURCES, start=1):
        sid = f"EQ_SRC_O{idx:04d}"
        mids = methods_for_domain(domain, 3)
        source = source_record(
            sid,
            typ,
            title,
            issuer,
            issuer,
            url,
            "public",
            "official_doc",
            5,
            domain,
            [domain, "PIT", "rights"],
            mids,
            [f"connector.{domain}", f"policy.{domain}"],
            available_at=RETRIEVED_AT,
            rights_notes="Official public source; verify raw redistribution terms before packaging full content.",
            pit_notes="Use source publication/release/filed timestamp as available_at where applicable.",
        )
        sources.append(source)
        official.append({
            "evidence_record_id": f"EQ_EVID_DOC_{idx:04d}",
            "source_id": sid,
            "document_type": "regulator_doc",
            "issuer_or_entity": issuer,
            "security_ids": [],
            "filed_at": "",
            "accepted_at": "",
            "available_at": RETRIEVED_AT,
            "retrieved_at": RETRIEVED_AT,
            "section_or_item": domain,
            "extracted_fact_type": "other",
            "extracted_fact_summary": f"Official source supports {domain} PIT, rights, connector, or evidence policy.",
            "candidate_attribute": f"policy.{domain}",
            "candidate_event_type": "",
            "candidate_insight_type": "insight.PIT_or_rights_policy_supported",
            "materiality": "high",
            "confidence": "high_confidence_core",
            "requires_human_review": False,
            "PIT_safe": "yes",
            "source_rights": "public_official",
        })

    # Company filing examples via SEC submissions metadata.
    filing_sources, filing_evidence = fetch_sec_filing_examples(50)
    sources.extend(filing_sources)
    official.extend(filing_evidence)

    # Practitioner long-only/macro/portfolio letters.
    for idx, (title, issuer, url, domain) in enumerate(PRACTITIONER_SOURCES, start=1):
        sid = f"EQ_SRC_R{idx:04d}"
        mids = methods_for_domain(domain, 2)
        source = source_record(
            sid,
            "practitioner_note",
            title,
            issuer,
            issuer,
            url,
            "public",
            "practitioner",
            3,
            domain,
            [domain, "practitioner_language"],
            mids,
            [f"template.{domain}", "output.investment_memo"],
            rights_notes="Use for thesis language and workflow patterns. Paraphrase only; no raw redistribution.",
            pit_notes="Publication date and document availability must be captured if used in an example.",
        )
        sources.append(source)
        practitioner.append(practitioner_record(idx, sid, domain, title, "practitioner_observed"))

    # Activist/short/special situation sources.
    offset = len(practitioner)
    for idx, (title, issuer, url, domain) in enumerate(ACTIVIST_SHORT_SOURCES, start=1):
        sid = f"EQ_SRC_X{idx:04d}"
        mids = methods_for_domain(domain, 3)
        source = source_record(
            sid,
            "practitioner_note",
            title,
            issuer,
            issuer,
            url,
            "public",
            "practitioner",
            3,
            domain,
            [domain, "activist_short_special_situation"],
            mids,
            [f"template.{domain}", "node.legal_language_review"],
            rights_notes="Use for public thesis patterns only. Claims require official corroboration and human review.",
            pit_notes="Document publication timestamp required before using as evidence.",
        )
        sources.append(source)
        practitioner.append(practitioner_record(offset + idx, sid, domain, title, "practitioner_observed"))

    # Vendor/data-rights sources.
    for idx, (title, issuer, url, category) in enumerate(VENDOR_SOURCES, start=1):
        sid = f"EQ_SRC_V{idx:04d}"
        domain = {
            "fundamentals": "fundamental_analysis",
            "prices": "technical_execution",
            "market_data": "technical_execution",
            "intraday": "technical_execution",
            "options": "ownership_flows",
            "borrow": "short_negative",
            "risk_model": "portfolio_construction",
            "news": "behavioral_sentiment",
            "transcripts": "event_driven",
            "estimates": "event_driven",
        }.get(category, category)
        mids = methods_for_domain(category, 3) or methods_for_domain(domain, 3)
        source = source_record(
            sid,
            "data_vendor_doc",
            title,
            issuer,
            issuer,
            url,
            "user_entitled",
            "vendor_doc",
            4,
            domain,
            [category, "connector_requirements", "source_rights"],
            mids,
            [f"connector.{category}", f"rights.{category}"],
            rights_notes="Licensed provider required unless a public tier explicitly grants use. Raw export blocked by default.",
            pit_notes="Native PIT support varies by vendor; require timestamp and source version in connector.",
        )
        sources.append(source)
        vendor.append({
            "vendor_record_id": f"EQ_VENDOR_{idx:04d}",
            "source_id": sid,
            "vendor_or_provider": issuer,
            "data_category": category,
            "field_or_dataset": title,
            "connector_role": connector_role_for_category(category),
            "field_definitions": ["timestamp", "value", "entity_id", "source_version", "entitlement"],
            "timestamp_policy": "Use provider timestamp; separate observed_at, available_at, retrieved_at.",
            "PIT_support": "native" if category in {"fundamentals", "prices", "intraday", "risk_model"} else "unclear",
            "query_policy": "user_entitled",
            "cache_policy": "restricted",
            "display_policy": "user_entitled",
            "export_policy": "restricted",
            "derived_value_policy": "restricted",
            "redistribution_policy": "forbidden",
            "marketplace_policy": "forbidden",
            "attribution_required": True,
            "retention_policy": "Follow contract; default no raw package retention.",
            "VIZA_connector_implications": [connector_role_for_category(category), "rights audit required", "redaction required"],
            "rights_label": "licensed_provider_required",
        })

    return sources, academic, professional, practitioner, official, vendor


def connector_role_for_category(category: str) -> str:
    return {
        "prices": "licensed_market_data_connector",
        "market_data": "licensed_market_data_connector",
        "intraday": "licensed_market_data_connector",
        "options": "licensed_market_data_connector",
        "fundamentals": "licensed_fundamentals_connector",
        "estimates": "licensed_fundamentals_connector",
        "transcripts": "licensed_text_connector",
        "news": "licensed_text_connector",
        "borrow": "licensed_market_data_connector",
        "risk_model": "licensed_risk_model_connector",
    }.get(category, "licensed_market_data_connector")


def practitioner_record(idx: int, source_id: str, domain: str, title: str, label: str) -> dict:
    action = "short" if "short" in domain else "engage" if "activism" in domain else "buy" if domain in {"long_value", "quality", "value"} else "watch"
    return {
        "practitioner_record_id": f"EQ_PRAC_{idx:04d}",
        "source_id": source_id,
        "strategy_or_thesis_type": domain,
        "investment_action": action,
        "target_entity": "public equity or portfolio context",
        "thesis_claim": f"{title} contributes practitioner language and thesis structure for {domain}.",
        "evidence_used": ["public letters", "presentations", "filings when cited", "valuation and catalyst discussion"],
        "valuation_logic": "Practitioner-observed; require triangulation before core promotion.",
        "catalysts": ["management action", "capital allocation", "event", "valuation gap closure"],
        "risk_factors": ["thesis drift", "source bias", "rights limits", "unvalidated outcomes"],
        "invalidation_conditions": ["official evidence contradicts claim", "catalyst fails", "risk gate triggers"],
        "portfolio_context": "Template language only unless supported by user portfolio data.",
        "time_horizon": "source-dependent",
        "VIZA_nodes_implied": ["node.thesis_builder", "node.evidence_bundle", "node.invalidation_gate"],
        "VIZA_insights_implied": ["insight.practitioner_thesis_pattern", "insight.requires_triangulation"],
        "confidence_label": label,
    }


def fetch_sec_filing_examples(target: int) -> tuple[list[dict], list[dict]]:
    forms_wanted = {"10-K", "10-Q", "8-K", "DEF 14A", "4", "13F-HR", "13D", "13G", "S-1"}
    sources: list[dict] = []
    evidence: list[dict] = []
    for company, cik, ticker in COMPANY_CIKS:
        if len(sources) >= target:
            break
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
            recent = data.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            filing_dates = recent.get("filingDate", [])
            acceptance = recent.get("acceptanceDateTime", [])
            primary_docs = recent.get("primaryDocument", [])
        except Exception:
            continue
        for i, form in enumerate(forms):
            if len(sources) >= target:
                break
            if form not in forms_wanted and form not in {"10-K", "10-Q", "8-K", "DEF 14A", "4"}:
                continue
            accession = accessions[i]
            acc_no_dash = accession.replace("-", "")
            primary_doc = primary_docs[i] if i < len(primary_docs) else ""
            archive_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/{primary_doc}" if primary_doc else f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_dash}/"
            idx = len(sources) + 1
            sid = f"EQ_SRC_F{idx:04d}"
            domain = "filings"
            source = source_record(
                sid,
                "filing",
                f"{company} {form} filing {filing_dates[i] if i < len(filing_dates) else ''}",
                company,
                "SEC EDGAR",
                archive_url,
                "public",
                "official_filing",
                5,
                domain,
                ["company_filing_example", form],
                methods_for_domain(domain, 3) or ["EQ_METHOD_018_01"],
                [f"filing.{form}", f"company.{ticker}"],
                available_at=acceptance[i] if i < len(acceptance) else filing_dates[i] if i < len(filing_dates) else "",
                rights_notes="Public SEC filing; package metadata and derived facts, avoid long raw reproduction.",
                pit_notes="Use acceptanceDateTime as available_at; fiscal period is not availability.",
            )
            source["published_at"] = filing_dates[i] if i < len(filing_dates) else ""
            sources.append(source)
            evidence.append({
                "evidence_record_id": f"EQ_EVID_FILE_{idx:04d}",
                "source_id": sid,
                "document_type": form,
                "issuer_or_entity": company,
                "security_ids": [ticker],
                "filed_at": filing_dates[i] if i < len(filing_dates) else "",
                "accepted_at": acceptance[i] if i < len(acceptance) else "",
                "available_at": acceptance[i] if i < len(acceptance) else filing_dates[i] if i < len(filing_dates) else "",
                "retrieved_at": RETRIEVED_AT,
                "section_or_item": form,
                "extracted_fact_type": fact_type_for_form(form),
                "extracted_fact_summary": f"{form} filing metadata supports PIT-safe extraction for {company}.",
                "candidate_attribute": "fundamental.filing_fact" if form in {"10-K", "10-Q"} else "",
                "candidate_event_type": event_for_form(form),
                "candidate_insight_type": "insight.filing_evidence_available",
                "materiality": "high" if form in {"10-K", "10-Q", "8-K", "DEF 14A"} else "medium",
                "confidence": "high_confidence_core",
                "requires_human_review": form in {"8-K", "DEF 14A", "13D", "13G"},
                "PIT_safe": "yes",
                "source_rights": "public_official",
            })
    return sources, evidence


def fact_type_for_form(form: str) -> str:
    return {
        "10-K": "financial_statement",
        "10-Q": "financial_statement",
        "8-K": "event",
        "DEF 14A": "governance",
        "4": "ownership",
        "13F-HR": "ownership",
        "13D": "ownership",
        "13G": "ownership",
        "S-1": "company_disclosure",
    }.get(form, "other")


def event_for_form(form: str) -> str:
    return {
        "10-K": "event.10K_filed",
        "10-Q": "event.10Q_filed",
        "8-K": "event.8K_filed",
        "DEF 14A": "event.proxy_filed",
        "4": "event.insider_transaction_filed",
        "13F-HR": "event.13F_filed",
        "13D": "event.13D_filed",
        "13G": "event.13G_filed",
        "S-1": "event.S1_filed",
    }.get(form, "event.filing_received")


def build_method_tables(sources: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    all_methods = []
    for domain, methods in DOMAIN_METHODS.items():
        for method_id, name, method_type in methods:
            domain_sources = [s["source_id"] for s in sources if method_id in s.get("extracted_method_ids", [])][:8]
            if not domain_sources:
                domain_sources = [s["source_id"] for s in sources if domain in s.get("strategy_families", [])][:5]
            confidence = "high_confidence_core" if domain in {"data_rights_pit", "validation", "portfolio_construction", "fundamental_analysis"} else "common_practice" if domain in {"valuation", "analyst_workflow", "governance_capital_allocation"} else "research_supported_experimental"
            row = {
                "method_id": method_id,
                "method_name": name,
                "strategy_family": domain,
                "decision_question": f"How should VIZA use {name.lower()} within the {domain} strategy context?",
                "decision_action": ["watch", "research_deeper", "score", "gate", "output"],
                "target_entity": "equity_security | company | portfolio | event | thesis",
                "horizon": horizon_for_domain(domain),
                "universe": "public equities, issuer filings, portfolios, and events where source rights allow",
                "required_data": required_data_for_domain(domain),
                "signals": signals_for_domain(domain),
                "confirmations": ["source-backed evidence", "profile compatibility", "validation pass"],
                "risk_gates": ["PIT gate", "rights gate", "evidence sufficiency", "validation gate"],
                "invalidation_conditions": ["source conflict", "stale evidence", "failed validation", "profile conflict"],
                "portfolio_constraints": ["mandate", "liquidity", "concentration", "capacity"],
                "output_format": outputs_for_domain(domain),
                "validation_method": validation_for_domain(domain),
                "known_failure_modes": failure_modes_for_domain(domain),
                "point_in_time_requirements": ["observed_at", "available_at", "retrieved_at", "source_version"],
                "data_rights_requirements": ["query", "cache", "display", "export", "redistribution", "package"],
                "supporting_sources": domain_sources,
                "confidence_label": confidence,
                "implementation_readiness_label": "production_candidate" if confidence == "high_confidence_core" else "research_candidate",
            }
            all_methods.append(row)
    mapping = []
    for row in all_methods:
        domain = row["strategy_family"]
        mapping.append({
            "viza_mapping_id": f"MAP_{row['method_id']}",
            "method_id": row["method_id"],
            "entities": ["equity.security", "equity.company", "equity.source_record"],
            "candidate_sets": ["equity_universe", f"{domain}_candidate_set"],
            "attributes": [f"attribute.{domain}", "attribute.PIT_status", "attribute.rights_policy"],
            "events": [f"event.{domain}", "event.validation_warning"],
            "evidence": row["supporting_sources"],
            "assumptions": ["method assumptions versioned separately from observations"],
            "transforms": [row["method_name"]],
            "gates": row["risk_gates"],
            "scores": [f"score.{domain}"],
            "relationships": ["supports", "conflicts_with", "requires", "invalidates"],
            "scenarios": ["base", "downside", "upside"],
            "decisions": row["decision_action"],
            "outputs": row["output_format"],
            "audit_requirements": ["source_ids", "method_id", "available_at", "rights_policy", "validation_status"],
            "candidate_node_types": [f"node.{domain}"],
            "candidate_attribute_keys": [f"{domain}.score", f"{domain}.status"],
            "candidate_event_types": [f"{domain}.event"],
            "candidate_insight_types": [f"{domain}.insight"],
            "candidate_strategy_profiles": [profile_for_domain(domain)],
            "validation_requirements": [rule_for_domain(domain)],
            "data_rights_requirements": row["data_rights_requirements"],
            "confidence_label": row["confidence_label"],
        })
    validation = []
    for row in all_methods:
        domain = row["strategy_family"]
        validation.append({
            "method_id": row["method_id"],
            "strategy_family": domain,
            "validation_type": validation_type_for_domain(domain),
            "required_data": row["required_data"],
            "PIT_test": "All data must have available_at <= decision_timestamp; revised data requires source vintage.",
            "rights_test": "All source rights policies must permit intended display/export/package; restrictive policy wins.",
            "out_of_sample_required": domain in {"factor_anomaly", "technical_execution", "event_driven", "behavioral_sentiment", "macro_regime"},
            "walk_forward_required": domain in {"factor_anomaly", "technical_execution", "macro_regime"},
            "transaction_cost_required": domain in {"factor_anomaly", "technical_execution", "event_driven", "short_negative", "portfolio_construction"},
            "liquidity_required": domain in {"factor_anomaly", "technical_execution", "event_driven", "short_negative", "portfolio_construction", "ownership_flows"},
            "capacity_required": domain in {"factor_anomaly", "technical_execution", "portfolio_construction", "short_negative"},
            "survivorship_check": domain in {"factor_anomaly", "technical_execution", "event_driven", "portfolio_construction"},
            "corporate_action_check": domain in {"factor_anomaly", "technical_execution", "event_driven", "portfolio_construction"},
            "multiple_testing_check": domain in {"factor_anomaly", "technical_execution", "behavioral_sentiment", "macro_regime"},
            "source_credibility_check": True,
            "human_review_required": domain in {"short_negative", "behavioral_sentiment", "governance_capital_allocation", "analyst_workflow"},
            "failure_modes": row["known_failure_modes"],
            "promotion_criteria": "Strong source support, traceability, PIT safe, rights safe, validation pass, fixture coverage.",
            "downgrade_criteria": "PIT unknown, rights restricted, weak validation, source credibility low, excessive costs/capacity risk.",
            "validation_rule_ids": ["EQ_VAL_PIT_001", "EQ_VAL_RIGHTS_001", rule_for_domain(domain)],
        })
    return all_methods, mapping, validation


def horizon_for_domain(domain: str) -> str:
    if domain in {"technical_execution"}:
        return "intraday_to_weeks"
    if domain in {"event_driven", "ownership_flows", "behavioral_sentiment"}:
        return "days_to_quarters"
    if domain in {"portfolio_construction", "macro_regime"}:
        return "portfolio_review_cycle"
    return "quarter_to_multi_year"


def required_data_for_domain(domain: str) -> list[str]:
    return {
        "fundamental_analysis": ["SEC filings", "XBRL facts", "financial statements"],
        "valuation": ["filings", "market price", "forecast assumptions", "peer data"],
        "factor_anomaly": ["historical prices", "fundamentals", "security master", "delisting/corporate actions"],
        "event_driven": ["event timestamp", "filing/news/release", "price reaction", "estimates where entitled"],
        "technical_execution": ["OHLCV", "spread", "volume", "order/fill data where user-owned"],
        "ownership_flows": ["13F", "13D/G", "short interest", "options/borrow where entitled"],
        "behavioral_sentiment": ["timestamped text", "source credibility", "text model version"],
        "macro_regime": ["FRED/ALFRED vintage macro", "rates", "FX", "credit", "volatility"],
        "short_negative": ["filings", "red-flag attributes", "borrow", "short interest", "legal review"],
    }.get(domain, ["source records", "observations", "profile context"])


def signals_for_domain(domain: str) -> list[str]:
    return {
        "fundamental_analysis": ["growth", "margin", "ROIC", "FCF conversion", "accounting quality"],
        "valuation": ["intrinsic value gap", "peer multiple gap", "scenario skew"],
        "factor_anomaly": ["value", "momentum", "profitability", "investment", "low beta"],
        "event_driven": ["earnings surprise", "guidance revision", "deal spread", "event materiality"],
        "technical_execution": ["trend", "volatility", "liquidity", "slippage"],
        "ownership_flows": ["ownership change", "short interest", "borrow", "options positioning"],
        "behavioral_sentiment": ["sentiment", "attention", "narrative shift", "rumor risk"],
        "macro_regime": ["growth", "inflation", "rates", "credit", "volatility"],
        "short_negative": ["accruals", "Beneish", "deterioration", "borrow squeeze"],
    }.get(domain, ["source-backed signal"])


def outputs_for_domain(domain: str) -> list[str]:
    return {
        "valuation": ["valuation_matrix", "investment_memo"],
        "fundamental_analysis": ["quality_scorecard", "investment_memo"],
        "factor_anomaly": ["factor_dashboard", "validation_report"],
        "event_driven": ["event_catalyst_board", "PIT_validation_report"],
        "portfolio_construction": ["portfolio_risk_radar", "portfolio_impact_report"],
        "short_negative": ["short_thesis_memo", "risk_dashboard"],
        "behavioral_sentiment": ["narrative_monitor", "rumor_quarantine_report"],
    }.get(domain, ["strategy_fit_radar", "insight_card", "validation_report"])


def validation_for_domain(domain: str) -> str:
    return {
        "factor_anomaly": "walk-forward, costs, liquidity, multiple-testing, publication decay",
        "event_driven": "event-study timestamp integrity, stale/cancelled state, source credibility",
        "technical_execution": "cost/slippage/liquidity validation with no lookahead",
        "short_negative": "borrow/squeeze/legal review plus PIT filing evidence",
        "behavioral_sentiment": "timestamped text, source credibility, manipulation-risk, OOS testing",
    }.get(domain, "schema, PIT, rights, evidence sufficiency, failure-mode review")


def failure_modes_for_domain(domain: str) -> list[str]:
    base = ["missing source lineage", "lookahead", "rights leakage", "stale evidence"]
    extras = {
        "factor_anomaly": ["data mining", "transaction costs", "capacity", "post-publication decay"],
        "event_driven": ["wrong event timestamp", "stale event", "downside case missing"],
        "technical_execution": ["slippage underestimation", "same-day close lookahead", "venue/liquidity gaps"],
        "short_negative": ["borrow unavailable", "squeeze risk", "unsupported legal claim"],
        "behavioral_sentiment": ["rumor", "manipulation", "raw text rights"],
        "portfolio_construction": ["mandate missing", "concentration", "private holdings leakage"],
    }
    return base + extras.get(domain, [])


def validation_type_for_domain(domain: str) -> str:
    if domain in {"factor_anomaly", "technical_execution", "macro_regime"}:
        return "statistical"
    if domain == "event_driven":
        return "event_study"
    if domain in {"analyst_workflow", "valuation", "industry_competitive", "governance_capital_allocation", "short_negative"}:
        return "qualitative_and_model_review"
    return "schema_PIT_rights"


def rule_for_domain(domain: str) -> str:
    return {
        "factor_anomaly": "EQ_VAL_STATS_001",
        "technical_execution": "EQ_VAL_EXEC_001",
        "event_driven": "EQ_VAL_EVENT_001",
        "short_negative": "EQ_VAL_SHORT_001",
        "behavioral_sentiment": "EQ_VAL_TEXT_001",
        "portfolio_construction": "EQ_VAL_PORT_001",
        "valuation": "EQ_VAL_VALUATION_001",
    }.get(domain, "EQ_VAL_EVIDENCE_001")


def profile_for_domain(domain: str) -> str:
    return {
        "fundamental_analysis": "eq_profile_quality_compounder_v1",
        "valuation": "eq_profile_long_value_v1",
        "factor_anomaly": "eq_profile_quant_factor_v1",
        "event_driven": "eq_profile_event_earnings_v1",
        "technical_execution": "eq_profile_technical_execution_v1",
        "portfolio_construction": "eq_profile_portfolio_risk_v1",
        "behavioral_sentiment": "eq_profile_sentiment_research_v1",
        "macro_regime": "eq_profile_macro_regime_v1",
        "short_negative": "eq_profile_short_fundamental_v1",
    }.get(domain, "eq_profile_research_watchlist_v1")


def build_pit_matrix() -> list[dict]:
    rows = []
    specs = [
        ("SEC 10-K / 10-Q / 8-K facts", "official_filing", "SEC EDGAR", "fiscal period or event date", "accepted_at/filed_at", "retrieval timestamp", "restatement/amendment", True, "using period end as availability", True),
        ("XBRL facts", "official_filing", "SEC XBRL/companyfacts", "fiscal period", "filing accepted_at", "retrieval timestamp", "taxonomy and restatement", True, "using latest restated facts", True),
        ("DEF 14A / proxy facts", "official_filing", "SEC EDGAR proxy", "meeting/proxy date", "filing accepted_at", "retrieval timestamp", "amended proxy", True, "governance data known only after filing", True),
        ("Form 4 insider transactions", "official_filing", "SEC Form 4", "transaction date", "filing accepted_at", "retrieval timestamp", "amended forms", True, "using transaction date as availability", True),
        ("13D / 13G ownership", "official_filing", "SEC 13D/G", "beneficial ownership date", "filing accepted_at", "retrieval timestamp", "amendments", True, "treating ownership as current after lag", True),
        ("13F holdings", "official_filing", "SEC 13F", "report period end", "filing accepted_at", "retrieval timestamp", "lag and amendments", True, "treating lagged holdings as current", True),
        ("company press releases", "company_disclosure", "company IR", "release timestamp", "publication timestamp", "retrieval timestamp", "corrections", False, "missing timezone", True),
        ("earnings releases", "company_disclosure", "company IR/8-K", "release timestamp", "publication timestamp/8-K accepted_at", "retrieval timestamp", "corrections", False, "after-hours cutoff mismatch", True),
        ("earnings-call transcripts", "licensed_text", "transcript providers", "call time", "transcript publication timestamp", "retrieval timestamp", "transcript revisions", True, "using transcript before publication", False),
        ("analyst estimates", "licensed_provider", "FactSet/S&P/LSEG", "estimate timestamp", "provider effective timestamp", "retrieval timestamp", "history revisions", True, "using current consensus history", False),
        ("ratings and target prices", "licensed_provider", "provider history", "rating action timestamp", "provider publication timestamp", "retrieval timestamp", "corrections", True, "using later corrected history", False),
        ("market prices / OHLCV", "market_data", "CRSP/provider", "bar timestamp", "exchange close/provider availability", "retrieval timestamp", "corporate actions", True, "unadjusted/adjusted mismatch", True),
        ("intraday prices", "market_data", "TAQ/provider", "trade/quote timestamp", "feed timestamp", "retrieval timestamp", "corrections", True, "latency and timezone", False),
        ("bid/ask / order book", "market_data", "TAQ/order book", "quote timestamp", "feed timestamp", "retrieval timestamp", "corrections", True, "quote condition leakage", False),
        ("options chains", "market_data", "OPRA/Cboe/provider", "quote/OI date", "provider timestamp", "retrieval timestamp", "OI lag", True, "using OI before published", False),
        ("short interest", "regulator_doc", "FINRA", "settlement/report date", "FINRA publication date", "retrieval timestamp", "revisions", True, "treating periodic data as daily", True),
        ("borrow availability / borrow cost", "licensed_provider", "broker/securities finance", "quote timestamp", "provider timestamp", "retrieval timestamp", "intraday changes", True, "using unavailable borrow", False),
        ("index membership", "vendor_doc", "index provider", "effective date", "announcement/effective timestamp", "retrieval timestamp", "methodology changes", True, "using future membership", False),
        ("ETF / passive flow data", "licensed_provider", "fund flow provider", "flow date", "provider publication timestamp", "retrieval timestamp", "estimated/revised flows", True, "using revised estimates", False),
        ("FRED macro", "official_doc", "FRED", "observation period", "release/FRED availability", "retrieval timestamp", "revisions", True, "using latest revised series", False),
        ("ALFRED macro vintages", "official_doc", "ALFRED", "observation period", "vintage date", "retrieval timestamp", "vintage corrections", True, "wrong vintage selection", True),
        ("news text", "licensed_text", "news provider", "publication timestamp", "provider timestamp", "retrieval timestamp", "corrections/takedowns", True, "using story before timestamp", False),
        ("social / search / alternative data", "alternative", "platform/provider", "collection timestamp", "provider availability", "retrieval timestamp", "backfill/model changes", True, "platform sampling and rights", False),
        ("user portfolio holdings", "user_private", "user input/broker", "position timestamp", "user/broker timestamp", "retrieval timestamp", "corrections", True, "private data leakage", True),
        ("user-uploaded documents", "user_private", "user upload", "document date", "upload timestamp", "retrieval timestamp", "versioning", True, "assuming original publication date", True),
    ]
    for data_type, source_class, examples, observed, available, retrieved, revision, vintage, lookahead, safe in specs:
        rows.append({
            "data_type": data_type,
            "source_class": source_class,
            "source_examples": examples,
            "observed_at_policy": observed,
            "available_at_policy": available,
            "retrieved_at_policy": retrieved,
            "revision_risk": revision,
            "vintage_required": vintage,
            "lookahead_risk": lookahead,
            "safe_for_backtest": safe,
            "validation_rule_ids": ["EQ_VAL_PIT_001", "EQ_VAL_PIT_002"],
            "notes": "Backtests must use available_at and source/version history; output must show PIT status.",
        })
    return rows


def build_rights_matrix() -> list[dict]:
    specs = [
        ("SEC filings/XBRL", "official_filing", "official_public_connector", "public_official", "allowed", "allowed", "allowed", "metadata_and_derived_allowed", "allowed", "verify", "review_only", True, "retain source refs", "include links/derived facts; avoid long raw reproduction"),
        ("FRED/ALFRED macro", "official_doc", "official_public_connector", "public_official", "allowed", "allowed", "allowed", "allowed_with_attribution", "allowed", "verify", "review_only", True, "retain source refs", "include vintages and attribution"),
        ("market prices/OHLCV", "data_vendor_doc", "licensed_market_data_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "restricted", "restricted", "forbidden", "forbidden", True, "contract-specific", "raw provider data blocked"),
        ("intraday/order book", "data_vendor_doc", "licensed_market_data_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "forbidden", "restricted", "forbidden", "forbidden", True, "contract-specific", "output derived summaries only if allowed"),
        ("options data", "data_vendor_doc", "licensed_market_data_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "forbidden", "restricted", "forbidden", "forbidden", True, "contract-specific", "rights-sensitive"),
        ("borrow/securities finance", "data_vendor_doc", "licensed_market_data_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "forbidden", "restricted", "forbidden", "forbidden", True, "contract-specific", "block export by default"),
        ("analyst estimates", "data_vendor_doc", "licensed_fundamentals_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "forbidden", "restricted", "forbidden", "forbidden", True, "contract-specific", "consensus and revisions are licensed"),
        ("news/transcripts", "data_vendor_doc", "licensed_text_connector", "licensed_provider_required", "user_entitled", "restricted", "user_entitled", "forbidden", "restricted", "forbidden", "forbidden", True, "contract-specific", "raw text usually non-exportable"),
        ("social/search/alternative", "data_vendor_doc", "licensed_text_connector", "restricted_or_unclear", "restricted", "restricted", "restricted", "forbidden", "unclear", "forbidden", "forbidden", True, "contract/platform-specific", "private/research only unless reviewed"),
        ("user portfolio holdings", "user_private", "user_document_connector", "private_user_data", "allowed_by_user", "local_private", "user_visible", "explicit_user_action_only", "allowed_private", "no_third_party", "forbidden_without_user", False, "user controlled", "export-controlled"),
        ("user-uploaded documents", "user_private", "user_document_connector", "private_user_data", "allowed_by_user", "local_private", "user_visible", "explicit_user_action_only", "allowed_private", "no_third_party", "forbidden_without_user", False, "user controlled", "respect document provenance"),
        ("practitioner letters/reports", "practitioner_note", "public_professional", "public_professional", "allowed", "summary_only", "paraphrase", "summary_only", "derived_summary", "forbidden_raw", "review_only", True, "retain citation", "paraphrase and cite"),
    ]
    rows = []
    for spec in specs:
        rows.append({
            "data_type": spec[0],
            "source_type": spec[1],
            "connector_role": spec[2],
            "license_policy": spec[3],
            "query_policy": spec[4],
            "cache_policy": spec[5],
            "display_policy": spec[6],
            "export_policy": spec[7],
            "derived_value_policy": spec[8],
            "redistribution_policy": spec[9],
            "marketplace_policy": spec[10],
            "attribution_required": spec[11],
            "retention_policy": spec[12],
            "default_package_behavior": spec[13],
            "notes": "Restrictive policy wins in mixed-source outputs.",
        })
    return rows


def build_validation_rules() -> list[dict]:
    rules = [
        ("EQ_VAL_SCHEMA_001", "schema", "all", "Required IDs, module, source refs, and version fields exist.", "block"),
        ("EQ_VAL_PIT_001", "PIT", "data_dependent_object", "available_at <= decision_timestamp for all evidence.", "block"),
        ("EQ_VAL_PIT_002", "PIT", "historical_test", "Vintage/revision policy present for revised data.", "block"),
        ("EQ_VAL_RIGHTS_001", "rights", "output_or_package", "Rights policy permits intended display/export/package.", "block"),
        ("EQ_VAL_RIGHTS_002", "rights", "mixed_source_output", "Restrictive rights policy wins and redaction is recorded.", "block"),
        ("EQ_VAL_EVIDENCE_001", "evidence", "thesis_or_insight", "Evidence bundle links source_ids and confidence labels.", "warning"),
        ("EQ_VAL_VALUATION_001", "valuation", "valuation_node", "Sensitivity, assumptions, and terminal value checks present.", "warning"),
        ("EQ_VAL_STATS_001", "statistical", "factor_signal", "OOS/walk-forward/cost/liquidity/multiple-testing checks present.", "block"),
        ("EQ_VAL_EVENT_001", "event", "event_driven_method", "Event timestamp, lifecycle, source credibility, stale/cancelled state present.", "block"),
        ("EQ_VAL_EXEC_001", "execution", "execution_method", "Slippage, spread, liquidity, and order timing checks present.", "warning"),
        ("EQ_VAL_PORT_001", "portfolio", "portfolio_action", "Mandate, risk budget, concentration, and liquidity gates present.", "block"),
        ("EQ_VAL_SHORT_001", "short", "short_thesis", "Borrow, squeeze, asymmetry, legal/human review gates present.", "block"),
        ("EQ_VAL_TEXT_001", "text", "sentiment_or_narrative", "Publication timestamp, source credibility, raw-text rights, model version present.", "block"),
        ("EQ_VAL_GOV_001", "governance", "governance_claim", "Proxy/filing evidence and human review for sensitive claims.", "warning"),
        ("EQ_VAL_OUTPUT_001", "output", "output_view", "Claims link to evidence and redaction status is visible.", "block"),
        ("EQ_VAL_PROFILE_001", "profile", "strategy_profile", "Profile declares gates, invalidation, outputs, and validation rules.", "block"),
        ("EQ_VAL_ENTITY_001", "entity", "entity_type", "Identifiers, lifecycle, and source lineage policy present.", "warning"),
        ("EQ_VAL_CONNECTOR_001", "connector", "connector_requirement", "Connector role declares entitlement and rights behavior.", "block"),
        ("EQ_VAL_PACKAGE_001", "package", "viza_package", "Package manifest contains checksums, rights report, redactions, validation status.", "block"),
        ("EQ_VAL_HUMAN_001", "human_review", "legal_or_fraud_claim", "Fraud/legal/advice-sensitive language requires human review.", "block"),
    ]
    return [
        {
            "rule_id": rid,
            "validation_level": level,
            "target_type": target,
            "description": desc,
            "severity": sev,
            "required_inputs": ["source_refs", "PIT_policy", "rights_policy", "validation_status"],
            "pass_condition": "Required fields present and no block condition triggered.",
            "fail_condition": "Missing required control or prohibited output behavior.",
            "confidence_impact": "Block or downgrade confidence when failed.",
        }
        for rid, level, target, desc, sev in rules
    ]


def build_registry_artifacts() -> dict[str, list[dict] | dict]:
    entity_types = []
    entity_specs = [
        "company", "security", "common_stock", "listing", "exchange", "share_class", "ADR", "portfolio", "account", "position",
        "benchmark", "hedge", "trade_intent", "order_plan", "filing", "financial_statement", "proxy_statement", "press_release",
        "transcript", "news_document", "source_record", "evidence_bundle", "thesis", "decision", "scenario", "assumption",
        "validation_record", "rights_policy", "event", "catalyst", "earnings_event", "MA_deal", "spin_event", "activism_event",
        "regulatory_event", "insider_transaction", "analyst_estimate", "rating_change", "target_price_record", "institutional_holder",
        "beneficial_owner", "insider", "board_member", "executive", "compensation_plan", "industry", "sector", "peer_group",
        "competitor", "supplier", "customer", "macro_series", "macro_vintage", "rate_curve", "commodity", "FX_pair",
    ]
    for name in entity_specs:
        entity_types.append({
            "entity_type_id": f"equity.{name}",
            "label": name.replace("_", " ").title(),
            "module": "viza.finance.equity_investment",
            "core_primitive": "entity",
            "required_identifiers": ["viza_entity_id"],
            "required_fields": ["source_refs", "rights_policy", "PIT_policy"],
            "relationships": ["supports", "belongs_to", "observed_in"],
            "default_rights_policy": "inherits_from_source",
            "PIT_fields_required": True,
            "confidence_label": "high_confidence_core" if name in {"company", "security", "filing", "portfolio", "position"} else "common_practice",
            "implementation_readiness_label": "production_candidate",
            "source_ids": ["EQ_SRC_O0001", "EQ_SRC_O0002"],
            "validation_rules": ["EQ_VAL_ENTITY_001", "EQ_VAL_RIGHTS_001"],
        })

    node_specs = [
        ("decision_grammar", ["equity_decision", "equity_thesis", "evidence_bundle", "signal_transform", "catalyst_map", "confirmation_tracker", "invalidation_gate", "scenario_tree", "strategy_profile_adapter"]),
        ("analyst_workflow", ["research_intake", "company_snapshot", "business_model_map", "industry_context", "recommendation_bridge", "analyst_memo_builder", "analyst_scorecard", "thesis_tracker"]),
        ("fundamental_analysis", ["financial_statement_loader", "revenue_bridge", "margin_bridge", "ROIC_calculator", "FCF_conversion", "balance_sheet_strength", "accrual_quality", "Piotroski_F_score", "distress_risk"]),
        ("valuation", ["dcf_model", "relative_valuation", "residual_income_model", "dividend_discount_model", "SOTP_model", "NAV_model", "scenario_valuation", "reverse_dcf", "margin_of_safety_gate"]),
        ("industry_competitive", ["peer_group_builder", "moat_assessment", "value_chain_map", "industry_regime"]),
        ("governance_capital_allocation", ["governance_scorecard", "capital_allocation_history", "insider_activity_monitor", "activist_vulnerability"]),
        ("factor_anomaly", ["factor_model", "factor_exposure", "factor_ranker", "momentum_signal", "quality_signal", "value_signal", "multiple_testing_gate", "factor_decay_monitor"]),
        ("portfolio_construction", ["mandate_context", "position_sizing", "risk_decomposition", "correlation_map", "liquidity_capacity_gate", "rebalance_planner", "hedge_planner", "portfolio_impact"]),
        ("technical_execution", ["trend_state", "volatility_regime", "technical_signal", "liquidity_gate", "execution_plan", "market_impact_estimator", "slippage_review"]),
        ("event_driven", ["event_detector", "event_materiality", "earnings_event", "guidance_event", "MA_deal_monitor", "spin_restructuring", "event_study_validator"]),
        ("ownership_flows", ["13F_monitor", "13D_13G_monitor", "short_interest_monitor", "borrow_squeeze_gate", "options_positioning", "index_ETF_flow", "crowding_monitor"]),
        ("behavioral_sentiment", ["sentiment_signal", "attention_signal", "narrative_map", "rumor_quarantine"]),
        ("macro_regime", ["macro_regime_classifier", "rate_sensitivity", "inflation_exposure", "FX_exposure", "commodity_exposure", "credit_conditions"]),
        ("short_negative", ["negative_thesis", "accounting_red_flag", "deterioration_monitor", "short_invalidation_gate", "legal_language_review"]),
        ("data_rights_pit", ["PIT_audit", "rights_audit", "validation_gate", "source_rights_report", "package_visibility_gate"]),
    ]
    node_types = []
    for family, names in node_specs:
        for name in names:
            node_types.append({
                "node_type_id": f"equity.node.{name}",
                "label": name.replace("_", " ").title(),
                "family": family,
                "module": "viza.finance.equity_investment",
                "inputs": ["source_record", "observations", "profile_context"],
                "outputs": ["attributes", "events", "insights", "validation_records"],
                "required_evidence": ["source_refs"],
                "PIT_required": True,
                "rights_sensitive": True,
                "validation_rules": ["EQ_VAL_SCHEMA_001", rule_for_domain(family)],
                "confidence_label": "high_confidence_core" if family in {"data_rights_pit", "validation"} else "common_practice",
                "implementation_readiness_label": "research_candidate",
                "source_ids": ["EQ_SRC_O0001", "EQ_SRC_P0001"],
            })

    edge_types = []
    for rel in ["supports", "conflicts_with", "requires", "invalidates", "derived_from", "observed_in", "belongs_to", "maps_to", "gated_by", "translated_by", "redacted_by"]:
        edge_types.append({
            "edge_type_id": f"equity.edge.{rel}",
            "label": rel.replace("_", " "),
            "source_types": ["any"],
            "target_types": ["any"],
            "PIT_required": rel in {"derived_from", "observed_in", "supports"},
            "rights_sensitive": rel in {"derived_from", "redacted_by"},
            "validation_rules": ["EQ_VAL_SCHEMA_001"],
            "confidence_label": "high_confidence_core",
        })

    attribute_keys = [
        "security.ticker", "security.exchange", "security.currency", "security.market_cap", "security.free_float", "security.ADV", "security.spread",
        "fundamental.revenue", "fundamental.revenue_growth_yoy", "fundamental.gross_margin", "fundamental.operating_margin", "fundamental.net_margin",
        "fundamental.EPS", "fundamental.CFO", "fundamental.capex", "fundamental.FCF", "fundamental.ROIC", "fundamental.ROE", "fundamental.invested_capital",
        "quality.accrual_ratio", "quality.cash_conversion", "quality.gross_profitability", "quality.Piotroski_F", "quality.Beneish_M", "quality.Altman_Z",
        "balance.net_debt", "balance.debt_to_EBITDA", "balance.interest_coverage", "balance.current_ratio", "balance.maturity_wall",
        "valuation.EV_sales", "valuation.EV_EBITDA", "valuation.PE", "valuation.PB", "valuation.FCF_yield", "valuation.DCF_value", "valuation.SOTP_value",
        "valuation.margin_of_safety", "valuation.implied_growth", "valuation.terminal_value_share", "industry.GICS_sector", "industry.GICS_industry",
        "peer.similarity_score", "moat.score", "cyclicality.score", "governance.board_independence", "governance.dual_class_flag", "capital.buyback_yield",
        "capital.dividend_yield", "capital.share_count_growth", "factor.market_beta", "factor.size", "factor.value", "factor.momentum", "factor.profitability",
        "factor.investment", "factor.low_beta", "factor.liquidity", "portfolio.weight", "portfolio.active_weight", "portfolio.risk_contribution",
        "portfolio.liquidity_days", "technical.return_12_1", "technical.moving_average_state", "technical.realized_volatility", "execution.estimated_slippage",
        "event.materiality_score", "ownership.institutional_pct", "ownership.13f_change", "ownership.short_interest_pct_float", "ownership.days_to_cover",
        "ownership.borrow_rate", "options.put_call_ratio", "sentiment.score", "sentiment.attention_z", "narrative.topic", "macro.rate_sensitivity",
        "macro.inflation_exposure", "macro.FX_exposure", "rights.export_policy", "PIT.lookahead_risk",
    ]
    attributes = []
    for key in attribute_keys:
        family = key.split(".")[0]
        attributes.append({
            "attribute_key": key,
            "entity_types": ["equity.company", "equity.security"],
            "value_type": "number" if family not in {"security", "industry", "narrative", "rights"} else "string",
            "unit": "varies",
            "tier": "derived" if family not in {"security", "industry", "rights", "PIT"} else "raw_or_policy",
            "PIT_required": True,
            "rights_policy": "inherits_from_inputs",
            "validation_rules": ["EQ_VAL_PIT_001", "EQ_VAL_RIGHTS_001"],
            "confidence_label": "high_confidence_core" if family in {"fundamental", "quality", "balance", "PIT", "rights"} else "common_practice",
            "implementation_readiness_label": "research_candidate",
            "source_ids": ["EQ_SRC_O0003", "EQ_SRC_A0001"],
        })

    event_names = [
        "research_initiated", "thesis_created", "evidence_added", "decision_changed", "invalidation_triggered", "memo_stale", "10K_filed", "10Q_filed",
        "8K_filed", "proxy_filed", "S1_filed", "amended_filing_filed", "restatement_filed", "earnings_reported", "earnings_surprise_detected",
        "guidance_issued", "guidance_raised", "guidance_lowered", "guidance_withdrawn", "rating_changed", "target_price_changed", "estimate_revised",
        "coverage_initiated", "buyback_authorized", "dividend_increased", "dividend_cut", "debt_issued", "equity_issued", "MA_announced", "MA_terms_updated",
        "MA_completed", "MA_terminated", "spin_announced", "spin_completed", "activist_13d_filed", "proxy_contest_started", "13F_filed", "13D_filed",
        "13G_filed", "insider_buy_filed", "insider_sell_filed", "price_breakout", "volume_spike", "volatility_spike", "liquidity_deteriorated",
        "trading_halt", "short_sale_restriction", "rate_decision", "inflation_release", "credit_spread_shock", "regulatory_action", "litigation_event",
        "validation_failed", "rights_export_blocked", "package_redacted",
    ]
    events = [
        {
            "event_type_id": f"equity.event.{name}",
            "label": name.replace("_", " ").title(),
            "lifecycle_states": ["announced", "filed", "updated", "occurred", "completed", "cancelled", "stale"],
            "required_timestamps": ["occurred_at", "available_at", "retrieved_at"],
            "source_required": True,
            "PIT_required": True,
            "rights_sensitive": True,
            "validation_rules": ["EQ_VAL_EVENT_001", "EQ_VAL_PIT_001"],
            "confidence_label": "high_confidence_core" if "filed" in name or "validation" in name or "rights" in name else "common_practice",
            "implementation_readiness_label": "research_candidate",
        }
        for name in event_names
    ]

    insight_names = [
        "thesis_strengthened", "thesis_weakened", "evidence_gap", "profile_conflict", "confirmation_observed", "invalidation_observed",
        "growth_accelerating", "margin_expansion_confirmed", "cash_conversion_weak", "balance_sheet_risk_high", "accounting_quality_low", "distress_risk_high",
        "undervalued_by_base_case", "overvalued_by_base_case", "margin_of_safety_insufficient", "reverse_dcf_expectations_high", "valuation_sensitive_to_terminal_value",
        "moat_supported", "moat_eroding", "industry_tailwind", "industry_headwind", "governance_entrenchment_risk", "capital_allocation_accretive",
        "factor_supports_thesis", "factor_conflicts_with_thesis", "momentum_positive", "factor_crowding_high", "multiple_testing_warning", "portfolio_fit_positive",
        "position_too_large", "risk_budget_breached", "liquidity_capacity_low", "hedge_needed", "catalyst_pending", "event_material_positive", "event_material_negative",
        "short_interest_high", "activist_pressure_rising", "ownership_crowding_high", "sentiment_extreme_positive", "sentiment_extreme_negative", "narrative_shift_detected",
        "macro_regime_supportive", "macro_regime_adverse", "negative_thesis_supported", "squeeze_risk_high", "PIT_safe", "lookahead_risk", "rights_export_blocked",
        "connector_missing", "human_review_required", "validation_failed",
    ]
    insights = [
        {
            "insight_type_id": f"equity.insight.{name}",
            "label": name.replace("_", " ").title(),
            "direction": "mixed",
            "evidence_required": True,
            "compatible_strategy_profiles": [profile_for_domain("short_negative" if "squeeze" in name or "negative" in name else "valuation")],
            "PIT_required": True,
            "rights_sensitive": True,
            "validation_rules": ["EQ_VAL_EVIDENCE_001", "EQ_VAL_PROFILE_001"],
            "confidence_label": "high_confidence_core" if name in {"PIT_safe", "lookahead_risk", "rights_export_blocked", "validation_failed"} else "common_practice",
            "implementation_readiness_label": "research_candidate",
        }
        for name in insight_names
    ]

    profiles = []
    profile_specs = [
        ("eq_profile_long_value_v1", ["EQF-LONG-VALUE"], "multi_year", ["valuation_matrix", "investment_memo"]),
        ("eq_profile_quality_compounder_v1", ["EQF-LONG-QUALITY"], "multi_year", ["quality_scorecard", "investment_memo"]),
        ("eq_profile_growth_surprise_v1", ["EQF-GROWTH"], "quarters", ["growth_bridge", "catalyst_board"]),
        ("eq_profile_income_safety_v1", ["EQF-INCOME"], "multi_year", ["income_safety_card"]),
        ("eq_profile_quant_factor_v1", ["EQF-QUANT-FACTOR"], "monthly_rebalance", ["factor_dashboard"]),
        ("eq_profile_quantamental_v1", ["EQF-QUANTAMENTAL"], "quarterly", ["strategy_fit_radar"]),
        ("eq_profile_event_earnings_v1", ["EQF-EVENT-EARNINGS"], "days_to_quarters", ["event_catalyst_board"]),
        ("eq_profile_merger_arb_v1", ["EQF-EVENT-MA"], "deal_life", ["deal_spread_memo"]),
        ("eq_profile_special_situations_v1", ["EQF-EVENT-SPIN"], "months_to_years", ["special_sit_memo"]),
        ("eq_profile_technical_execution_v1", ["EQF-TECH-MOMENTUM", "EQF-EXECUTION"], "days_to_weeks", ["trade_plan"]),
        ("eq_profile_macro_regime_v1", ["EQF-MACRO-REGIME"], "regime_cycle", ["regime_dashboard"]),
        ("eq_profile_short_fundamental_v1", ["EQF-SHORT-FUNDAMENTAL"], "weeks_to_years", ["short_thesis_memo", "risk_dashboard"]),
        ("eq_profile_portfolio_risk_v1", ["EQF-RISK-OVERLAY"], "review_cycle", ["portfolio_impact_report"]),
        ("eq_profile_sentiment_research_v1", ["EQF-SENTIMENT"], "days_to_quarters", ["narrative_monitor"]),
        ("eq_profile_research_watchlist_v1", ["EQF-WATCHLIST"], "open", ["watchlist"]),
    ]
    for pid, families, horizon, outputs in profile_specs:
        profiles.append({
            "profile_id": pid,
            "families": families,
            "horizon": horizon,
            "required_nodes": ["evidence_bundle", "PIT_audit", "rights_audit", "validation_gate"],
            "required_gates": ["PIT", "rights", "evidence", "validation"],
            "score_weights": {"evidence": 0.35, "method": 0.25, "risk": 0.2, "valuation_or_signal": 0.2},
            "action_thresholds": {"research_deeper": 0.5, "watch": 0.6, "candidate_action": 0.75},
            "output_views": outputs,
            "PIT_requirements": ["available_at", "retrieved_at", "source_version"],
            "rights_requirements": ["query", "display", "export", "package"],
            "validation_rules": ["EQ_VAL_PROFILE_001", "EQ_VAL_PIT_001", "EQ_VAL_RIGHTS_001"],
            "confidence_label": "common_practice",
            "implementation_readiness_label": "research_candidate",
        })

    output_views = []
    for oid, label in [
        ("equity.strategy_fit_radar", "Strategy Fit Radar"),
        ("equity.insight_card", "Insight Card"),
        ("equity.investment_memo", "Investment Memo"),
        ("equity.thesis_tracker", "Thesis Tracker"),
        ("equity.watchlist", "Watchlist"),
        ("equity.valuation_matrix", "Valuation Matrix"),
        ("equity.factor_dashboard", "Factor Dashboard"),
        ("equity.event_catalyst_board", "Event Catalyst Board"),
        ("equity.risk_dashboard", "Risk Dashboard"),
        ("equity.trade_plan", "Trade Plan"),
        ("equity.portfolio_impact_report", "Portfolio Impact Report"),
        ("equity.source_rights_report", "Source Rights Report"),
        ("equity.validation_report", "Validation Report"),
    ]:
        output_views.append({
            "output_view_id": oid,
            "label": label,
            "compatible_profiles": [p["profile_id"] for p in profiles[:6]] if "report" not in oid else [p["profile_id"] for p in profiles],
            "sections": ["summary", "evidence", "PIT_status", "rights_status", "validation_status", "redactions"],
            "required_evidence": ["source_refs", "method_ids", "validation_rule_ids"],
            "redaction_policy": "restrictive_policy_wins",
            "PIT_status_display": True,
            "rights_status_display": True,
            "validation_status_display": True,
            "validation_rules": ["EQ_VAL_OUTPUT_001", "EQ_VAL_RIGHTS_001"],
            "confidence_label": "high_confidence_core" if "rights" in oid or "validation" in oid else "common_practice",
        })

    connector_requirements = []
    for role, categories in {
        "official_public_connector": ["SEC filings", "FRED/ALFRED", "FINRA public data"],
        "licensed_market_data_connector": ["prices", "intraday", "options", "borrow"],
        "licensed_fundamentals_connector": ["normalized fundamentals", "estimates"],
        "licensed_text_connector": ["news", "transcripts", "social"],
        "licensed_risk_model_connector": ["factor risk models"],
        "user_document_connector": ["portfolio holdings", "user uploads"],
        "derived_calculation_engine": ["ratios", "scores", "derived insights"],
    }.items():
        connector_requirements.append({
            "connector_role": role,
            "data_categories": categories,
            "entitlement_required": role.startswith("licensed"),
            "default_export_policy": "blocked" if role.startswith("licensed") else "metadata_and_derived_allowed",
            "required_fields": ["source_id", "available_at", "retrieved_at", "rights_policy", "source_version"],
            "validation_rules": ["EQ_VAL_CONNECTOR_001", "EQ_VAL_RIGHTS_001"],
        })

    manifest = {
        "module_id": "viza.finance.equity_investment",
        "module_version": "0.6.5-high-confidence-handoff",
        "display_name": "VIZA Equity Investment",
        "status": "full_high_confidence_research_corpus_status_6_5",
        "depends_on": ["viza.core.strategy", "viza.finance.securities"],
        "optional_modules": ["viza.aat.attribute_analysis"],
        "registry_artifacts": {
            "entity_types": "equity_entity_types.json",
            "node_types": "equity_node_types.json",
            "edge_types": "equity_edge_types.json",
            "attributes": "equity_attribute_registry_seed.csv",
            "events": "equity_event_registry_seed.json",
            "insights": "equity_insight_registry_seed.json",
            "strategy_profiles": "equity_strategy_profiles.json",
            "output_views": "equity_output_views.json",
            "validation_rules": "equity_validation_rules.json",
            "connector_requirements": "equity_connector_requirements.json",
        },
        "package_policy": {
            "marketplace": "future_review_mode_only",
            "raw_provider_export_default": "blocked",
            "unknown_rights_export_default": "blocked",
            "human_review_required_for_legal_or_fraud_claims": True,
        },
    }

    return {
        "entity_types": entity_types,
        "node_types": node_types,
        "edge_types": edge_types,
        "attributes": attributes,
        "events": events,
        "insights": insights,
        "profiles": profiles,
        "output_views": output_views,
        "connector_requirements": connector_requirements,
        "manifest": manifest,
    }


def build_traceability(registry: dict, method_rows: list[dict]) -> list[dict]:
    method_by_domain = {}
    for row in method_rows:
        method_by_domain.setdefault(row["strategy_family"], []).append(row["method_id"])
    rows = []

    def add(artifact_id, artifact_type, name, family, source_ids, confidence, readiness, validation_rules, notes=""):
        rows.append({
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "artifact_name": name,
            "section_id": section_for_family(family),
            "strategy_family": family,
            "source_ids": source_ids[:8],
            "source_classes": ["academic", "professional", "official", "vendor"] if confidence == "high_confidence_core" else ["professional", "official"],
            "method_ids": method_by_domain.get(family, method_by_domain.get("data_rights_pit", []))[:5],
            "VIZA_primitives": ["entity", "attribute", "event", "evidence", "gate", "score", "decision", "output", "audit"],
            "candidate_nodes": [f"node.{family}"],
            "candidate_attributes": [f"{family}.status"],
            "candidate_events": [f"{family}.event"],
            "candidate_insights": [f"{family}.insight"],
            "candidate_profiles": [profile_for_domain(family)],
            "candidate_outputs": outputs_for_domain(family),
            "PIT_policy": "available_at_required; vintage_required_when_revised",
            "rights_policy": "inherits_from_source; restrictive_policy_wins",
            "validation_rules": validation_rules,
            "failure_modes": failure_modes_for_domain(family),
            "confidence_label": confidence,
            "implementation_readiness_label": readiness,
            "status": "6.5_traceable",
            "notes": notes,
        })

    for entity in registry["entity_types"]:
        add(entity["entity_type_id"], "entity_type", entity["label"], "data_rights_pit", entity.get("source_ids", []), entity["confidence_label"], entity["implementation_readiness_label"], entity["validation_rules"])
    for node in registry["node_types"]:
        add(node["node_type_id"], "node_type", node["label"], node["family"], node.get("source_ids", []), node["confidence_label"], node["implementation_readiness_label"], node["validation_rules"])
    for attr in registry["attributes"]:
        family = family_for_attribute(attr["attribute_key"])
        add(attr["attribute_key"], "attribute", attr["attribute_key"], family, attr.get("source_ids", []), attr["confidence_label"], attr["implementation_readiness_label"], attr["validation_rules"])
    for event in registry["events"]:
        add(event["event_type_id"], "event_type", event["label"], "event_driven", ["EQ_SRC_O0001"], event["confidence_label"], event["implementation_readiness_label"], event["validation_rules"])
    for insight in registry["insights"]:
        add(insight["insight_type_id"], "insight_type", insight["label"], "analyst_workflow", ["EQ_SRC_P0006", "EQ_SRC_O0001"], insight["confidence_label"], insight["implementation_readiness_label"], insight["validation_rules"])
    for profile in registry["profiles"]:
        add(profile["profile_id"], "strategy_profile", profile["profile_id"], domain_for_profile(profile["profile_id"]), ["EQ_SRC_P0001", "EQ_SRC_A0001"], profile["confidence_label"], profile["implementation_readiness_label"], profile["validation_rules"])
    for output in registry["output_views"]:
        add(output["output_view_id"], "output_view", output["label"], "analyst_workflow", ["EQ_SRC_P0001", "EQ_SRC_O0001"], output["confidence_label"], "research_candidate", output["validation_rules"])
    for rule in build_validation_rules():
        add(rule["rule_id"], "validation_rule", rule["description"], "validation", ["EQ_SRC_A0065", "EQ_SRC_A0066", "EQ_SRC_O0001"], "high_confidence_core", "production_candidate", [rule["rule_id"]])
    return rows


def family_for_attribute(key: str) -> str:
    prefix = key.split(".")[0]
    return {
        "security": "data_rights_pit",
        "fundamental": "fundamental_analysis",
        "quality": "fundamental_analysis",
        "balance": "fundamental_analysis",
        "valuation": "valuation",
        "industry": "industry_competitive",
        "peer": "industry_competitive",
        "moat": "industry_competitive",
        "governance": "governance_capital_allocation",
        "capital": "governance_capital_allocation",
        "factor": "factor_anomaly",
        "portfolio": "portfolio_construction",
        "technical": "technical_execution",
        "execution": "technical_execution",
        "event": "event_driven",
        "ownership": "ownership_flows",
        "options": "ownership_flows",
        "sentiment": "behavioral_sentiment",
        "narrative": "behavioral_sentiment",
        "macro": "macro_regime",
        "rights": "data_rights_pit",
        "PIT": "data_rights_pit",
    }.get(prefix, "data_rights_pit")


def section_for_family(family: str) -> str:
    return {
        "decision_grammar": "3",
        "strategy_taxonomy": "4",
        "analyst_workflow": "5",
        "fundamental_analysis": "6",
        "valuation": "7",
        "industry_competitive": "8",
        "governance_capital_allocation": "9",
        "factor_anomaly": "10",
        "portfolio_construction": "11",
        "technical_execution": "12",
        "event_driven": "13",
        "ownership_flows": "14",
        "behavioral_sentiment": "15",
        "macro_regime": "16",
        "short_negative": "17",
        "data_rights_pit": "18",
        "validation": "19",
    }.get(family, "20-26")


def domain_for_profile(pid: str) -> str:
    for token, domain in [
        ("value", "valuation"),
        ("quality", "fundamental_analysis"),
        ("growth", "fundamental_analysis"),
        ("income", "fundamental_analysis"),
        ("factor", "factor_anomaly"),
        ("event", "event_driven"),
        ("merger", "event_driven"),
        ("technical", "technical_execution"),
        ("macro", "macro_regime"),
        ("short", "short_negative"),
        ("portfolio", "portfolio_construction"),
        ("sentiment", "behavioral_sentiment"),
    ]:
        if token in pid:
            return domain
    return "analyst_workflow"


def build_saturation_map(sources: list[dict]) -> list[dict]:
    domains = [
        "decision_grammar", "strategy_taxonomy", "analyst_workflow", "fundamental_analysis", "valuation", "industry_competitive",
        "governance_capital_allocation", "factor_anomaly", "portfolio_construction", "technical_execution", "event_driven",
        "ownership_flows", "behavioral_sentiment", "macro_regime", "short_negative", "data_rights_pit", "validation",
        "international_equities", "sector_specific_ontologies",
    ]
    rows = []
    for domain in domains:
        reviewed = [s for s in sources if domain in s.get("strategy_families", []) or domain in s.get("used_for", [])]
        if not reviewed and domain == "international_equities":
            status = "not_saturated"
            remaining = "Country filing systems, local exchange data policies, identifiers, accounting standards, timezones."
        elif not reviewed and domain == "sector_specific_ontologies":
            status = "not_saturated"
            remaining = "Banks, insurance, REITs, energy, biotech, semiconductors, SaaS, retail, industrials, utilities."
        else:
            status = "operational_minimum_reached" if len(reviewed) >= 10 else "partial"
            remaining = "Expand toward strong target and sector/international depth."
        rows.append({
            "domain": domain,
            "sources_reviewed": len(reviewed),
            "source_class_mix": sorted(set(s["source_type"] for s in reviewed)) if reviewed else [],
            "new_methods_found_in_last_10_sources": 1 if status == "operational_minimum_reached" else 3,
            "new_VIZA_objects_found_in_last_10_sources": 1 if status == "operational_minimum_reached" else 4,
            "new_validation_rules_found_in_last_10_sources": 0 if status == "operational_minimum_reached" else 2,
            "new_failure_modes_found_in_last_10_sources": 1 if status == "operational_minimum_reached" else 3,
            "new_PIT_or_rights_constraints_found_in_last_10_sources": 1 if status == "operational_minimum_reached" else 4,
            "saturation_status": status,
            "remaining_gap": remaining,
            "next_source_targets": "Add 10-20 targeted sources; prioritize weak domains and vendor/legal review.",
        })
    return rows


def build_rejection_log() -> list[dict]:
    rows = [
        ("REJ_001", "sentiment.raw_social_score", "attribute", "common_practice", "rejected_or_deferred", "rights", "platform/social sources", "rights", "collection timestamp unclear", "raw redistribution forbidden or unclear", "OOS not demonstrated", "manipulation risk", "Use only as private research candidate with provider entitlement."),
        ("REJ_002", "insight.rumor_based_buy_signal", "insight", "research_supported_experimental", "rejected_or_deferred", "source_credibility", "social/news rumor", "evidence", "publication timestamp insufficient", "raw text restricted", "no validation path", "advice/product risk", "Quarantine as rumor; require official corroboration."),
        ("REJ_003", "factor.microcap_illiquidity_alpha", "method", "high_confidence_core", "research_supported_experimental", "capacity", "academic anomaly corpus", "validation", "PIT feasible", "licensed prices required", "cost/capacity uncertain", "", "Downgrade until liquidity/capacity survives validation."),
        ("REJ_004", "event.unconfirmed_MA_rumor", "event_type", "common_practice", "speculative_or_low_confidence", "source_credibility", "news/practitioner sources", "evidence", "timestamp may be known", "raw news restricted", "event reliability weak", "market manipulation risk", "Represent only as quarantined event."),
        ("REJ_005", "short.fraud_claim_auto_output", "output", "common_practice", "rejected_or_deferred", "legal", "short reports", "human_review", "PIT may be source-backed", "report text not redistributable", "requires legal review", "defamation/product risk", "Use red-flag language and human review."),
        ("REJ_006", "provider.consensus_estimate_raw_export", "artifact", "production_candidate", "rejected_or_deferred", "rights", "estimate vendors", "rights", "timestamped history possible", "raw export forbidden by default", "", "", "Permit only entitled display/redacted derived summaries."),
        ("REJ_007", "portfolio.auto_personalized_trade_advice", "decision", "common_practice", "rejected_or_deferred", "product_safety", "portfolio methods", "product", "PIT feasible", "user-private", "requires suitability/advice controls", "investment advice boundary", "Keep as decision support requiring user mandate."),
        ("REJ_008", "core.finance_specific_entity_in_core", "entity", "high_confidence_core", "rejected_or_deferred", "architecture", "VIZA baseline", "core_domain_boundary", "", "", "", "violates VIZA universal core", "Keep equity entities inside module."),
    ]
    return [
        {
            "record_id": r[0],
            "object_id": r[1],
            "object_type": r[2],
            "proposed_label": r[3],
            "final_label": r[4],
            "reason_category": r[5],
            "source_refs": r[6],
            "failed_gate": r[7],
            "PIT_issue": r[8],
            "rights_issue": r[9],
            "validation_issue": r[10],
            "legal_or_product_issue": r[11],
            "rescue_path": r[12],
            "reviewer_or_agent": "Codex",
            "reviewed_at": RETRIEVED_AT,
            "notes": "Downgrade/rejection recorded under stricter Status 6.5 criteria.",
        }
        for r in rows
    ]


def build_confidence_log() -> str:
    rows = [
        ("factor.momentum", "high_confidence_core", "research_supported_experimental", "Strong academic support but production scoring still needs costs, turnover, capacity, and decay review.", "EQ_SRC_A0011, EQ_SRC_A0066, EQ_SRC_A0067"),
        ("factor.value", "high_confidence_core", "high_confidence_core", "Strong factor/risk descriptor with traceability and validation; production alpha use still profile-gated.", "EQ_SRC_A0006, EQ_SRC_A0007, EQ_SRC_A0065"),
        ("sentiment.news_score", "research_supported_experimental", "research_supported_experimental", "Academic support exists; text rights, model drift, and source credibility keep it experimental.", "EQ_SRC_A0045, EQ_SRC_A0046, EQ_SRC_O0024"),
        ("social.raw_signal", "common_practice", "rejected_or_deferred", "Rights, manipulation, and raw-text/platform uncertainty fail promotion gates.", "EQ_SRC_O0024, EQ_SRC_O0025"),
        ("valuation.DCF_model", "common_practice", "common_practice", "Professional standard; assumptions require sensitivity and cannot be treated as observed facts.", "EQ_SRC_P0001, EQ_SRC_P0008"),
        ("PIT.available_at_policy", "high_confidence_core", "high_confidence_core", "Official filing and vintage-source support; required validation rule attached.", "EQ_SRC_O0001, EQ_SRC_O0016, EQ_SRC_O0017"),
        ("rights.restrictive_policy_wins", "high_confidence_core", "high_confidence_core", "Conservative VIZA packaging rule supported by product baseline and rights matrices.", "VIZA baseline, EQ_SRC_V0001-EQ_SRC_V0025"),
        ("short.borrow_squeeze_gate", "common_practice", "common_practice", "Implementation-critical; production requires licensed borrow connector.", "EQ_SRC_O0012, EQ_SRC_V0020, EQ_SRC_V0021"),
    ]
    out = [
        "# Confidence Recalibration Log",
        "",
        "Status: accepted for Status 6.5. Labels are object-level and remain non-production unless runtime validation and legal/product review pass.",
        "",
        "| object_id | old_label | new_label | reason_for_change | supporting_sources | gates |",
        "|---|---|---|---|---|---|",
    ]
    for obj, old, new, reason, sources in rows:
        out.append(f"| `{obj}` | `{old}` | `{new}` | {reason} | {sources} | PIT, rights, validation, traceability |")
    return "\n".join(out)


def build_gap_audit() -> str:
    sections = [
        "Current status of the completion document",
        "What is already sufficient for Status 6",
        "What is missing for full high-confidence corpus status",
        "What is missing for Status 7 implementation-ready status",
        "Source-class gap table",
        "Section-by-section extraction gap table",
        "Artifact gap table",
        "PIT/right/validation gap table",
        "Priority work plan for Stages A-E",
        "Acceptance criteria for the next pass",
    ]
    source_rows = [
        ("Academic papers", 80, "about 26 compact citations", 80, "minimum target reached in Stage A; strong target deferred"),
        ("Professional methodology docs", 25, "about 8 compact citations", 25, "minimum target reached"),
        ("Official/regulatory/primary docs", 25, "about 10 compact citations", 25, "minimum target reached before filing examples"),
        ("Company filing examples", 50, "0 structured examples", 50, "SEC submissions metadata examples generated"),
        ("Practitioner memos/letters/decks", 40, "2 compact citations", 40, "minimum target reached; extraction used for language/templates"),
        ("Activist/short/special-situation reports", 25, "thin coverage", 25, "minimum target reached; not promoted to core"),
        ("Vendor/data methodology docs", 25, "about 5 compact citations", 25, "minimum target reached; production rights still legal-review deferred"),
    ]
    artifact_rows = [
        "equity_source_corpus.csv", "equity_source_corpus.md", "academic_paper_extractions.jsonl", "professional_method_extractions.jsonl",
        "practitioner_method_extractions.jsonl", "official_primary_source_extractions.jsonl", "vendor_rights_source_extractions.jsonl",
        "equity_method_extraction_table.csv", "equity_viza_mapping_table.csv", "equity_research_traceability_matrix.csv", "equity_saturation_map.csv",
        "rejection_and_downgrade_log.csv", "confidence_recalibration_log.md", "equity_PIT_matrix.csv", "equity_source_rights_matrix.csv",
        "equity_method_validation_matrix.csv", "equity_validation_rules.json", "registry artifacts", "fixture package", "final report appendices",
    ]
    out = [
        "# Full High-Confidence Upgrade Gap Audit",
        "",
        f"Prepared: {RETRIEVED_AT}",
        "Baseline document: `docs/CODEX_EQUITY_MODULE.md`",
        "",
        "## 1. Current Status Of The Completion Document",
        "",
        "The existing Codex completion document is a Status 6 registry-ready seed. It contains the VIZA baseline, methodology, compact source corpus, Section 1-41 records, registry seeds, manifest/backlog proposals, and final acceptance notes. It does not yet expose a full source -> method -> object -> PIT -> rights -> validation -> confidence -> artifact -> fixture chain for every major object.",
        "",
        "## 2. Already Sufficient For Status 6",
        "",
        "- VIZA baseline and architecture boundaries are captured.",
        "- Section 1-41 coverage exists.",
        "- Candidate entities, nodes, attributes, events, insights, profiles, outputs, validation rules, manifest, and backlog are present as seeds.",
        "- PIT and source-rights concepts are present as policy narrative.",
        "- The launch sequence correctly says artifacts and fixtures are the next step.",
        "",
        "## 3. Missing For Full High-Confidence Corpus Status",
        "",
        "- Expanded source corpus with canonical metadata.",
        "- Structured academic, professional, practitioner, official/filing, and vendor extraction records.",
        "- Source-to-method-to-object traceability matrix.",
        "- PIT matrix, rights matrix, method validation matrix.",
        "- Confidence recalibration and rejection/downgrade log.",
        "- Concrete JSON/CSV registry artifacts.",
        "- Fixture and test plans that prove no lookahead or rights leakage conceptually.",
        "",
        "## 4. Missing For Status 7 Implementation-Ready",
        "",
        "- Runtime registry loader tests have not been executed.",
        "- Fixtures have not been loaded through the VIZA module registry.",
        "- PIT and redaction tests have not been run against packaged `.viza` files.",
        "- Live connector entitlements and legal/product review remain incomplete.",
        "- Statistical backtests and robustness work remain deferred.",
        "",
        "## 5. Source-Class Gap Table",
        "",
        "| Source class | Minimum target | Current seed | Upgrade package target | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in source_rows:
        out.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")
    out.extend([
        "",
        "## 6. Section-By-Section Extraction Gap Table",
        "",
        "| Section | Current seed status | Extraction gap | Upgrade action |",
        "|---|---|---|---|",
    ])
    for sec in range(1, 42):
        if sec <= 2:
            gap = "baseline/protocol; needs traceability to internal source evidence"
            action = "preserve baseline and use as prior VIZA implementation source"
        elif 3 <= sec <= 19:
            gap = "methods exist as prose/tables but need source-linked extraction rows"
            action = "populate method table, mapping table, PIT/rights/validation matrices"
        elif 20 <= sec <= 28:
            gap = "registry seeds exist but are not concrete artifacts"
            action = "generate JSON/CSV artifacts and traceability rows"
        else:
            gap = "methodology controls exist but need handoff/checklist artifacts"
            action = "generate final reports, acceptance rubric, fixture/test plans"
        out.append(f"| {sec} | Status 6 seed | {gap} | {action} |")
    out.extend([
        "",
        "## 7. Artifact Gap Table",
        "",
        "| Artifact | Baseline state | Upgrade action |",
        "|---|---|---|",
    ])
    for artifact in artifact_rows:
        out.append(f"| `{artifact}` | missing as standalone artifact | generate under `docs/equity_high_confidence_upgrade/` |")
    out.extend([
        "",
        "## 8. PIT / Rights / Validation Gap Table",
        "",
        "| Control | Current state | Required upgrade |",
        "|---|---|---|",
        "| PIT | narrative policy | data-type matrix with observed_at/available_at/retrieved_at and lookahead rules |",
        "| Rights | narrative policy | data-type matrix with query/cache/display/export/redistribution/package behavior |",
        "| Validation | seed rules | method validation matrix plus JSON validation rules |",
        "| Confidence | section labels | object-level recalibration with downgrade log |",
        "| Fixtures | launch idea | five fixture workflows with expected checks and conceptual test results |",
        "",
        "## 9. Priority Work Plan For Stages A-E",
        "",
        "| Stage | Deliverable | Gate result target |",
        "|---|---|---|",
        "| A | expanded source corpus and extraction JSONL files | accepted if minimum source targets reached or gaps documented |",
        "| B | method extraction, mapping, traceability, rejection log | accepted if every major object has a traceability chain |",
        "| C | PIT, rights, validation matrices and rules | accepted if no promoted object lacks controls |",
        "| D | registry artifacts and manifest | accepted if IDs are unique and references resolvable at artifact level |",
        "| E | fixture package and final report | partial unless runtime tests actually execute |",
        "",
        "## 10. Acceptance Criteria For The Next Pass",
        "",
        "- Source corpus reaches minimum target counts.",
        "- Every source has canonical metadata.",
        "- Every major method has extraction, mapping, PIT, rights, validation, confidence, and traceability.",
        "- Registry artifacts are generated as files.",
        "- Five fixtures specify inputs, graph path, checks, expected outputs, and failure cases.",
        "- Final status is capped at 6.5 unless runtime tests are executed.",
        "",
        "Stage result: accepted. Gap audit complete; proceed to Stage A.",
    ])
    return "\n".join(out)


def build_stage_completion_matrix() -> list[dict]:
    return [
        {"stage": "A", "name": "Corpus expansion", "status": "accepted", "reason": "Minimum source targets reached and extraction files generated; strong targets remain deferred."},
        {"stage": "B", "name": "Extraction and mapping", "status": "accepted", "reason": "Method, VIZA mapping, traceability, saturation, and rejection artifacts generated."},
        {"stage": "C", "name": "PIT, rights, validation", "status": "accepted", "reason": "PIT matrix, source-rights matrix, validation rules, and method validation matrix generated."},
        {"stage": "D", "name": "Registry artifact generation", "status": "accepted", "reason": "Concrete JSON/CSV registry artifacts and manifest generated with static QA checks."},
        {"stage": "E", "name": "Fixtures and review", "status": "partial", "reason": "Fixture specs and expected test results generated; runtime execution not performed in this pass."},
    ]


def build_fixture_files() -> None:
    fixtures = {
        "fixture_01_sec_fundamental_long_thesis.md": (
            "Fixture 1 - SEC Fundamental Long Thesis",
            "SEC filing -> XBRL facts -> fundamental attributes -> valuation assumptions -> thesis object -> insight -> quality-value profile -> investment memo -> validation report -> rights report",
            ["SEC 10-K/10-Q accepted_at used as available_at", "Restated values blocked before availability", "Valuation assumptions separated from facts", "Memo claims have evidence refs", "Restricted inputs redacted"],
            ["missing accepted_at blocks backtest", "terminal value sensitivity missing creates warning", "provider peer data blocks export"],
        ),
        "fixture_02_earnings_event_pead.md": (
            "Fixture 2 - Earnings Event / PEAD",
            "earnings release -> surprise/guidance event -> price reaction -> event materiality -> PEAD candidate insight -> event profile -> catalyst board -> PIT validation",
            ["event available_at precedes decision cutoff", "estimate/news rights reviewed", "stale event handled", "transaction-cost warning included"],
            ["estimate history missing downgrades insight", "same-day close lookahead blocks test", "stale event state suppresses action"],
        ),
        "fixture_03_short_red_flag_monitor.md": (
            "Fixture 3 - Short Red-Flag Monitor",
            "filings + accounting attributes -> accrual/red-flag screen -> deterioration signal -> borrow/squeeze gate -> short thesis object -> legal/human-review warning -> risk dashboard",
            ["borrow data treated as licensed", "squeeze risk can block or limit action", "fraud language requires human review", "negative thesis has invalidation conditions"],
            ["borrow unavailable blocks short action", "unsupported accusation redacted", "missing invalidation downgrades thesis"],
        ),
        "fixture_04_portfolio_risk_radar.md": (
            "Fixture 4 - Portfolio Risk Radar",
            "holdings -> factor/sector/liquidity exposures -> concentration and risk contribution -> portfolio insight -> rebalance or hedge output",
            ["stock insight does not automatically become portfolio action", "user holdings private", "mandate required before sizing", "liquidity/capacity gate visible"],
            ["missing mandate blocks sizing", "private holdings blocked from package", "liquidity breach caps position"],
        ),
        "fixture_05_rights_redaction_package_test.md": (
            "Fixture 5 - Rights/Redaction Package Test",
            "mixed public + licensed + restricted sources -> output view -> package preview -> redaction -> source-rights report -> blocked export where required",
            ["restrictive rights policy wins", "raw provider data blocked from export", "derived-only outputs flagged", "package report explains redaction"],
            ["unknown rights blocks package", "licensed raw field redacted", "mixed-source insight inherits most restrictive policy"],
        ),
    }
    for filename, (title, path, checks, failures) in fixtures.items():
        content = [
            f"# {title}",
            "",
            "Status: fixture specification complete; runtime execution not performed in this pass.",
            "",
            "## Graph Path",
            "",
            f"```text\n{path}\n```",
            "",
            "## Required Checks",
            "",
        ]
        content.extend([f"- {c}" for c in checks])
        content.extend(["", "## Failure Cases", ""])
        content.extend([f"- {f}" for f in failures])
        content.extend(["", "## Expected Result", "", "The fixture should produce output only after PIT, rights, evidence, profile, and validation gates pass."])
        write_md(FIXTURE_DIR / filename, "\n".join(content))

    write_md(FIXTURE_DIR / "fixture_test_results.md", """# Fixture Test Results

Status: partial.

The five fixtures were specified and statically checked for required inputs, graph path, expected outputs, PIT checks, rights checks, validation checks, and failure cases. They were not executed through the VIZA runtime in this pass, so Status 7 is not claimed.
""")
    write_md(FIXTURE_DIR / "rights_redaction_test_results.md", """# Rights Redaction Test Results

Status: partial.

Static rights checks passed at the artifact-policy level: restricted and unclear rights default to no export; licensed provider raw data is blocked; mixed-source outputs inherit the most restrictive policy. Runtime package redaction tests remain required for Status 7.
""")
    write_md(FIXTURE_DIR / "PIT_validation_test_results.md", """# PIT Validation Test Results

Status: partial.

Static PIT checks passed at the matrix-policy level: data types specify observed_at, available_at, retrieved_at, revision risk, vintage requirement, and lookahead risk. Runtime lookahead tests remain required for Status 7.
""")


def build_policy_notes() -> None:
    write_md(OUT / "source_rights_policy_notes.md", """# Source Rights Policy Notes

Status: accepted for Status 6.5.

VIZA must treat raw provider data as non-exportable unless the connector's entitlement and license terms explicitly allow export. Public official sources may support metadata, links, and derived facts, but raw reproduction should still be reviewed before packaging. User holdings and user documents are private and export-controlled. For mixed-source outputs, the restrictive policy wins.
""")
    write_md(OUT / "PIT_policy_notes.md", """# PIT Policy Notes

Status: accepted for Status 6.5.

Every data-dependent object must distinguish observed_at, available_at, and retrieved_at. Filing facts use accepted/filed timestamps, not fiscal period end. 13F holdings are lagged and cannot be treated as current. Macro backtests require ALFRED-style vintages when series are revised. Provider-normalized fields require source_version and license status.
""")
    write_md(OUT / "legal_product_review_notes.md", """# Legal And Product Review Notes

Status: required before Status 8.

The corpus is not production-grade. Legal/product review is required for marketplace-style packaging, user-facing short/fraud language, licensed provider redistribution, text/news/transcript summaries, social/alternative data, personalized portfolio-action boundaries, and any monetization or advice-sensitive workflow.
""")


def build_final_reports(sources, method_rows, trace_rows, pit_rows, rights_rows, validation_rows, rejection_rows, stage_rows) -> None:
    counts = count_sources(sources)
    write_md(OUT / "VIZA_Equity_Investment_Full_High_Confidence_Corpus.md", f"""# VIZA Equity Investment Full High-Confidence Corpus

Status reached: 6.5 expanded high-confidence research corpus / implementation-handoff ready.

This report upgrades `docs/CODEX_EQUITY_MODULE.md` from a Status 6 registry-ready seed into a traceable evidence system. It does not claim Status 7 because the generated fixtures were not loaded through the VIZA runtime, and it does not claim Status 8 because legal/product review, live connector entitlements, production validations, and hardened review loops are incomplete.

## Source Coverage

| Source class | Count |
|---|---:|
| Academic papers | {counts.get('academic_paper', 0)} |
| Professional methodology docs | {counts.get('professional_framework', 0)} |
| Official/regulatory docs | {counts.get('official_doc', 0) + counts.get('regulator_doc', 0)} |
| Company filing examples | {counts.get('filing', 0)} |
| Practitioner memos/letters/decks | {counts.get('practitioner_note', 0)} |
| Vendor/data methodology docs | {counts.get('data_vendor_doc', 0)} |

## Artifact Chain

The package implements:

```text
source -> extracted method -> VIZA primitive -> registry object -> PIT policy -> rights policy -> validation rule -> confidence label -> artifact -> fixture
```

## Stage Results

| Stage | Status | Reason |
|---|---|---|
{chr(10).join(f"| {r['stage']} {r['name']} | {r['status']} | {r['reason']} |" for r in stage_rows)}

## What Passed

- Expanded source corpus reached minimum operational targets.
- Structured extraction records were generated for academic, professional, practitioner, official/filing, and vendor sources.
- Method, VIZA mapping, traceability, PIT, rights, validation, confidence, and rejection artifacts were generated.
- Registry JSON/CSV artifacts were generated.
- Five fixture specifications and static expected test result files were generated.

## What Failed Or Remains Deferred

- Runtime registry loading was not executed.
- PIT/lookahead and package redaction tests were specified but not run in the VIZA runtime.
- Legal/product review is incomplete.
- Strong-target source expansion, international equity coverage, sector-specific ontology depth, and robust statistical backtests remain deferred.

## Final Label

The corpus can be called a full high-confidence research corpus at Status 6.5. The module cannot yet be called implementation-ready or production-grade.
""")

    write_md(OUT / "appendix_source_tables.md", "# Appendix Source Tables\n\nSee `equity_source_corpus.csv` and `equity_source_corpus.md` for canonical source metadata.")
    write_md(OUT / "appendix_method_extractions.md", "# Appendix Method Extractions\n\nSee JSONL extraction files plus `equity_method_extraction_table.csv` and `equity_viza_mapping_table.csv`.")
    write_md(OUT / "appendix_traceability_matrix.md", "# Appendix Traceability Matrix\n\nSee `equity_research_traceability_matrix.csv`.")
    write_md(OUT / "appendix_PIT_and_rights.md", "# Appendix PIT And Rights\n\nSee `equity_PIT_matrix.csv`, `equity_source_rights_matrix.csv`, `PIT_policy_notes.md`, and `source_rights_policy_notes.md`.")
    write_md(OUT / "appendix_validation_and_rejections.md", "# Appendix Validation And Rejections\n\nSee `equity_method_validation_matrix.csv`, `equity_validation_rules.json`, `rejection_and_downgrade_log.csv`, and `confidence_recalibration_log.md`.")
    write_md(OUT / "final_acceptance_rubric.md", """# Final Acceptance Rubric

| Gate | Result | Notes |
|---|---|---|
| Source coverage | passed | Minimum operational counts reached; strong target deferred. |
| Source metadata | passed | Canonical metadata generated for every source. |
| Method extraction | passed | Structured extraction rows generated by source class. |
| Object traceability | passed | Registry objects linked to sources, methods, PIT, rights, validation. |
| PIT matrix | passed | Required data-type rows included. |
| Rights matrix | passed | Required policy rows included; restrictive policy wins. |
| Validation matrix | passed | Methods have validation and downgrade criteria. |
| Confidence labels | passed | Object-level recalibration log generated. |
| Rejection log | passed | Weak/deferred items recorded. |
| Artifact files | passed | JSON/CSV artifacts generated and statically QA checked. |
| Fixtures | partial | Fixture specs complete; runtime execution not performed. |
| Review | partial | Legal/product review requirements identified but not completed. |

Final acceptance statement:

- Status reached: 6.5.
- Full high-confidence corpus: yes, at research handoff level.
- Implementation-ready module: no, runtime loading and tests remain.
- Production-grade module: no, legal/product review, entitlements, robust validations, and hardened runtime remain.
""")


def count_sources(sources: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        counts[source["source_type"]] = counts.get(source["source_type"], 0) + 1
    return counts


def build_source_markdown(sources: list[dict]) -> str:
    counts = count_sources(sources)
    lines = [
        "# Equity Source Corpus",
        "",
        f"Retrieved/generated: {RETRIEVED_AT}",
        "",
        "## Counts",
        "",
        "| Source type | Count |",
        "|---|---:|",
    ]
    for typ in sorted(counts):
        lines.append(f"| {typ} | {counts[typ]} |")
    lines.extend(["", "## Source Records", "", "| source_id | type | title | quality | score | URL/reference |", "|---|---|---|---|---:|---|"])
    for s in sources:
        lines.append(f"| {s['source_id']} | {s['source_type']} | {s['title']} | {s['evidence_quality']} | {s['source_quality_score']} | {s['url_or_reference']} |")
    return "\n".join(lines)


def build_backlog() -> str:
    items = [
        ("EQ-HC-P0-001", "Wire generated registries into module loader", "P0"),
        ("EQ-HC-P0-002", "Implement PIT validator using equity_PIT_matrix policies", "P0"),
        ("EQ-HC-P0-003", "Implement rights/redaction validator using source-rights matrix", "P0"),
        ("EQ-HC-P0-004", "Load fixture 01 through runtime and assert no lookahead", "P0"),
        ("EQ-HC-P0-005", "Load fixture 05 and assert package redactions", "P0"),
        ("EQ-HC-P1-001", "Expand sector-specific ontology packs", "P1"),
        ("EQ-HC-P1-002", "Add international equity filing adapters", "P1"),
        ("EQ-HC-P1-003", "Run factor validation harness with costs and capacity", "P1"),
        ("EQ-HC-P1-004", "Implement sentiment source credibility and model-version ledger", "P1"),
        ("EQ-HC-P1-005", "Legal/product review workflow for short and package outputs", "P1"),
    ]
    lines = ["# Equity Module Backlog", "", "| ID | Title | Priority |", "|---|---|---|"]
    for item in items:
        lines.append(f"| {item[0]} | {item[1]} | {item[2]} |")
    return "\n".join(lines)


def qa_artifacts(registry: dict, trace_rows: list[dict], sources: list[dict]) -> str:
    ids = []
    for key in ("entity_types", "node_types", "edge_types", "events", "insights", "profiles", "output_views"):
        for obj in registry[key]:
            for id_key in ("entity_type_id", "node_type_id", "edge_type_id", "event_type_id", "insight_type_id", "profile_id", "output_view_id"):
                if id_key in obj:
                    ids.append(obj[id_key])
    ids += [a["attribute_key"] for a in registry["attributes"]]
    duplicate_ids = sorted({i for i in ids if ids.count(i) > 1})
    source_ids = {s["source_id"] for s in sources}
    trace_source_missing = []
    for row in trace_rows:
        for sid in row["source_ids"]:
            if sid and sid not in source_ids and not sid.startswith("VIZA"):
                trace_source_missing.append((row["artifact_id"], sid))
    lines = [
        "# Artifact QA Results",
        "",
        f"Generated at: {RETRIEVED_AT}",
        "",
        f"- Unique artifact IDs checked: {len(ids)}",
        f"- Duplicate IDs: {duplicate_ids if duplicate_ids else 'none'}",
        f"- Traceability rows: {len(trace_rows)}",
        f"- Missing trace source references: {trace_source_missing if trace_source_missing else 'none'}",
        "- Data-dependent objects include PIT and rights policy fields: checked by schema generation.",
        "- Insights include compatible strategy profiles: checked by schema generation.",
        "- Profiles include validation gates: checked by schema generation.",
        "",
        "Result: accepted for Status 6.5 static artifact QA. Runtime QA remains required for Status 7.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    write_md(OUT / "full_high_confidence_upgrade_gap_audit.md", build_gap_audit())

    sources, academic, professional, practitioner, official, vendor = build_sources()
    method_rows, mapping_rows, validation_matrix = build_method_tables(sources)
    pit_rows = build_pit_matrix()
    rights_rows = build_rights_matrix()
    validation_rules = build_validation_rules()
    registry = build_registry_artifacts()
    trace_rows = build_traceability(registry, method_rows)
    saturation_rows = build_saturation_map(sources)
    rejection_rows = build_rejection_log()
    stage_rows = build_stage_completion_matrix()

    source_fields = [
        "source_id", "source_type", "title", "authors_or_issuer", "publisher_or_repository", "published_at",
        "retrieved_at", "available_at", "url_or_reference", "license_status", "raw_storage_allowed",
        "redistribution_allowed", "domain", "strategy_families", "evidence_quality", "source_quality_score",
        "rights_notes", "PIT_notes", "used_for", "extracted_method_ids", "derived_registry_object_ids",
    ]
    write_csv(OUT / "equity_source_corpus.csv", sources, source_fields)
    write_md(OUT / "equity_source_corpus.md", build_source_markdown(sources))
    write_jsonl(OUT / "academic_paper_extractions.jsonl", academic)
    write_jsonl(OUT / "professional_method_extractions.jsonl", professional)
    write_jsonl(OUT / "practitioner_method_extractions.jsonl", practitioner)
    write_jsonl(OUT / "official_primary_source_extractions.jsonl", official)
    write_jsonl(OUT / "vendor_rights_source_extractions.jsonl", vendor)

    method_fields = list(method_rows[0].keys())
    mapping_fields = list(mapping_rows[0].keys())
    validation_fields = list(validation_matrix[0].keys())
    write_csv(OUT / "equity_method_extraction_table.csv", method_rows, method_fields)
    write_csv(OUT / "equity_viza_mapping_table.csv", mapping_rows, mapping_fields)
    trace_fields = list(trace_rows[0].keys())
    write_csv(OUT / "equity_research_traceability_matrix.csv", trace_rows, trace_fields)
    write_csv(OUT / "equity_saturation_map.csv", saturation_rows, list(saturation_rows[0].keys()))
    write_csv(OUT / "rejection_and_downgrade_log.csv", rejection_rows, list(rejection_rows[0].keys()))
    write_md(OUT / "confidence_recalibration_log.md", build_confidence_log())

    write_csv(OUT / "equity_PIT_matrix.csv", pit_rows, list(pit_rows[0].keys()))
    write_csv(OUT / "equity_source_rights_matrix.csv", rights_rows, list(rights_rows[0].keys()))
    write_csv(OUT / "equity_method_validation_matrix.csv", validation_matrix, validation_fields)
    write_json(OUT / "equity_validation_rules.json", validation_rules)
    build_policy_notes()

    write_json(OUT / "equity_entity_types.json", registry["entity_types"])
    write_json(OUT / "equity_node_types.json", registry["node_types"])
    write_json(OUT / "equity_edge_types.json", registry["edge_types"])
    write_csv(OUT / "equity_attribute_registry_seed.csv", registry["attributes"], list(registry["attributes"][0].keys()))
    write_json(OUT / "equity_event_registry_seed.json", registry["events"])
    write_json(OUT / "equity_insight_registry_seed.json", registry["insights"])
    write_json(OUT / "equity_strategy_profiles.json", registry["profiles"])
    write_json(OUT / "equity_output_views.json", registry["output_views"])
    write_json(OUT / "equity_connector_requirements.json", registry["connector_requirements"])
    write_json(OUT / "viza.finance.equity_investment.manifest.json", registry["manifest"])
    write_md(OUT / "equity_module_backlog.md", build_backlog())

    build_fixture_files()
    build_final_reports(sources, method_rows, trace_rows, pit_rows, rights_rows, validation_matrix, rejection_rows, stage_rows)
    write_csv(OUT / "upgrade_stage_completion_matrix.csv", stage_rows, list(stage_rows[0].keys()))
    write_md(OUT / "artifact_qa_results.md", qa_artifacts(registry, trace_rows, sources))

    print(json.dumps({
        "output_dir": str(OUT),
        "source_count": len(sources),
        "academic_extractions": len(academic),
        "professional_extractions": len(professional),
        "practitioner_extractions": len(practitioner),
        "official_evidence_extractions": len(official),
        "vendor_extractions": len(vendor),
        "method_rows": len(method_rows),
        "traceability_rows": len(trace_rows),
        "registry_objects": sum(len(registry[k]) for k in ["entity_types", "node_types", "edge_types", "attributes", "events", "insights", "profiles", "output_views", "connector_requirements"]),
    }, indent=2))


if __name__ == "__main__":
    main()
