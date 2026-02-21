"""
Seed script for Uzbek Banking Chart of Accounts (COA)
Based on Central Bank of Uzbekistan regulations

Run with: python -m scripts.seed_coa
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine, Base
from app.models.coa import (
    AccountClass, AccountGroup, AccountCategory, Account, AccountMapping,
    AccountClassType, AccountNature
)
from app.models.business_unit import BusinessUnit, AccountResponsibility, BusinessUnitType


def seed_account_classes(db):
    """Seed 5 main account classes"""
    classes = [
        {
            "code": "1",
            "name_en": "Assets",
            "name_uz": "Aktivlar",
            "class_type": AccountClassType.ASSETS,
            "nature": AccountNature.DEBIT,
            "description": "Bank assets that generate income",
            "display_order": 1
        },
        {
            "code": "2",
            "name_en": "Liabilities",
            "name_uz": "Majburiyatlar",
            "class_type": AccountClassType.LIABILITIES,
            "nature": AccountNature.CREDIT,
            "description": "Bank's funding sources",
            "display_order": 2
        },
        {
            "code": "3",
            "name_en": "Equity",
            "name_uz": "Xususiy kapital",
            "class_type": AccountClassType.EQUITY,
            "nature": AccountNature.CREDIT,
            "description": "Bank's own capital",
            "display_order": 3
        },
        {
            "code": "4",
            "name_en": "Revenue",
            "name_uz": "Daromadlar",
            "class_type": AccountClassType.REVENUE,
            "nature": AccountNature.CREDIT,
            "description": "Income from operations",
            "display_order": 4
        },
        {
            "code": "5",
            "name_en": "Expenses",
            "name_uz": "Xarajatlar",
            "class_type": AccountClassType.EXPENSES,
            "nature": AccountNature.DEBIT,
            "description": "Operating and financial expenses",
            "display_order": 5
        }
    ]
    
    created = 0
    for cls_data in classes:
        existing = db.query(AccountClass).filter(AccountClass.code == cls_data["code"]).first()
        if not existing:
            db.add(AccountClass(**cls_data))
            created += 1
    
    db.commit()
    print(f"Created {created} account classes")
    return created


def seed_account_groups(db):
    """Seed account groups (2-digit level)"""
    
    class_map = {c.code: c.id for c in db.query(AccountClass).all()}
    
    groups = [
        # Class 1 - Assets
        {"code": "10", "class_id": class_map["1"], "name_en": "Cash and Cash Equivalents", "name_uz": "Naqd pul va ekvivalentlar", "display_order": 1},
        {"code": "11", "class_id": class_map["1"], "name_en": "Due from Central Bank", "name_uz": "Markaziy bankdagi mablag'lar", "display_order": 2},
        {"code": "12", "class_id": class_map["1"], "name_en": "Loans to Customers", "name_uz": "Mijozlarga kreditlar", "display_order": 3},
        {"code": "13", "class_id": class_map["1"], "name_en": "Loans to Legal Entities", "name_uz": "Yuridik shaxslarga kreditlar", "display_order": 4},
        {"code": "14", "class_id": class_map["1"], "name_en": "Consumer Loans", "name_uz": "Iste'mol kreditlari", "display_order": 5},
        {"code": "15", "class_id": class_map["1"], "name_en": "Mortgage Loans", "name_uz": "Ipoteka kreditlari", "display_order": 6},
        {"code": "16", "class_id": class_map["1"], "name_en": "Due from Other Banks", "name_uz": "Boshqa banklardagi mablag'lar", "display_order": 7},
        {"code": "17", "class_id": class_map["1"], "name_en": "Investment Securities", "name_uz": "Investitsiya qimmatli qog'ozlari", "display_order": 8},
        {"code": "18", "class_id": class_map["1"], "name_en": "Fixed Assets", "name_uz": "Asosiy vositalar", "display_order": 9},
        {"code": "19", "class_id": class_map["1"], "name_en": "Other Assets", "name_uz": "Boshqa aktivlar", "display_order": 10},
        
        # Class 2 - Liabilities
        {"code": "20", "class_id": class_map["2"], "name_en": "Customer Deposits", "name_uz": "Mijozlar depozitlari", "display_order": 1},
        {"code": "21", "class_id": class_map["2"], "name_en": "Due to Central Bank", "name_uz": "Markaziy bankka majburiyatlar", "display_order": 2},
        {"code": "22", "class_id": class_map["2"], "name_en": "Due to Other Banks", "name_uz": "Boshqa banklarga majburiyatlar", "display_order": 3},
        {"code": "23", "class_id": class_map["2"], "name_en": "Debt Securities Issued", "name_uz": "Chiqarilgan qarz qimmatli qog'ozlari", "display_order": 4},
        {"code": "24", "class_id": class_map["2"], "name_en": "Borrowings from IFIs", "name_uz": "XMT dan qarzlar", "display_order": 5},
        {"code": "25", "class_id": class_map["2"], "name_en": "Other Liabilities", "name_uz": "Boshqa majburiyatlar", "display_order": 6},
        
        # Class 3 - Equity
        {"code": "30", "class_id": class_map["3"], "name_en": "Share Capital", "name_uz": "Ustav kapitali", "display_order": 1},
        {"code": "31", "class_id": class_map["3"], "name_en": "Reserves", "name_uz": "Zaxira fondi", "display_order": 2},
        {"code": "32", "class_id": class_map["3"], "name_en": "Retained Earnings", "name_uz": "Taqsimlanmagan foyda", "display_order": 3},
        
        # Class 4 - Revenue
        {"code": "40", "class_id": class_map["4"], "name_en": "Interest Income - Loans", "name_uz": "Foiz daromadi - Kreditlar", "display_order": 1},
        {"code": "41", "class_id": class_map["4"], "name_en": "Interest Income - Securities", "name_uz": "Foiz daromadi - Qimmatli qog'ozlar", "display_order": 2},
        {"code": "42", "class_id": class_map["4"], "name_en": "Interest Income - Banks", "name_uz": "Foiz daromadi - Banklar", "display_order": 3},
        {"code": "43", "class_id": class_map["4"], "name_en": "Fee and Commission Income", "name_uz": "Komissiya daromadi", "display_order": 4},
        {"code": "44", "class_id": class_map["4"], "name_en": "FX Trading Income", "name_uz": "Valyuta savdosi daromadi", "display_order": 4},
        {"code": "45", "class_id": class_map["4"], "name_en": "Other Operating Income", "name_uz": "Boshqa operatsion daromad", "display_order": 5},
        
        # Class 5 - Expenses
        {"code": "50", "class_id": class_map["5"], "name_en": "Interest Expense - Deposits", "name_uz": "Foiz xarajati - Depozitlar", "display_order": 1},
        {"code": "51", "class_id": class_map["5"], "name_en": "Interest Expense - Borrowings", "name_uz": "Foiz xarajati - Qarzlar", "display_order": 2},
        {"code": "52", "class_id": class_map["5"], "name_en": "Fee and Commission Expense", "name_uz": "Komissiya xarajati", "display_order": 3},
        {"code": "53", "class_id": class_map["5"], "name_en": "Personnel Expenses", "name_uz": "Xodimlar xarajati", "display_order": 4},
        {"code": "54", "class_id": class_map["5"], "name_en": "Administrative Expenses", "name_uz": "Ma'muriy xarajatlar", "display_order": 5},
        {"code": "55", "class_id": class_map["5"], "name_en": "Depreciation", "name_uz": "Amortizatsiya", "display_order": 6},
        {"code": "56", "class_id": class_map["5"], "name_en": "Provisions", "name_uz": "Zaxiralar", "display_order": 7},
        {"code": "57", "class_id": class_map["5"], "name_en": "Other Operating Expenses", "name_uz": "Boshqa operatsion xarajatlar", "display_order": 8},
    ]
    
    created = 0
    for grp_data in groups:
        existing = db.query(AccountGroup).filter(AccountGroup.code == grp_data["code"]).first()
        if not existing:
            db.add(AccountGroup(**grp_data))
            created += 1
    
    db.commit()
    print(f"Created {created} account groups")
    return created


def seed_account_categories(db):
    """Seed account categories (3-digit level)"""
    
    group_map = {g.code: g.id for g in db.query(AccountGroup).all()}
    
    categories = [
        # 10x - Cash
        {"code": "101", "group_id": group_map["10"], "name_en": "Cash in Vault - UZS", "name_uz": "Kassadagi naqd pul - UZS"},
        {"code": "102", "group_id": group_map["10"], "name_en": "Cash in Vault - Foreign Currency", "name_uz": "Kassadagi naqd pul - Valyuta"},
        {"code": "103", "group_id": group_map["10"], "name_en": "Cash in ATMs", "name_uz": "Bankomatdagi naqd pul"},
        
        # 11x - Central Bank
        {"code": "111", "group_id": group_map["11"], "name_en": "Required Reserves - UZS", "name_uz": "Majburiy zaxiralar - UZS"},
        {"code": "112", "group_id": group_map["11"], "name_en": "Required Reserves - FCY", "name_uz": "Majburiy zaxiralar - Valyuta"},
        {"code": "113", "group_id": group_map["11"], "name_en": "Correspondent Account - CB", "name_uz": "Korrespondent hisob - MB"},
        
        # 12x - Loans to Customers (Short-term)
        {"code": "121", "group_id": group_map["12"], "name_en": "Short-term Corporate Loans", "name_uz": "Qisqa muddatli korporativ kreditlar"},
        {"code": "122", "group_id": group_map["12"], "name_en": "Short-term SME Loans", "name_uz": "Qisqa muddatli KOB kreditlari"},
        {"code": "123", "group_id": group_map["12"], "name_en": "Overdrafts", "name_uz": "Overdraftlar"},
        
        # 13x - Loans to Legal Entities (Long-term)
        {"code": "131", "group_id": group_map["13"], "name_en": "Long-term Corporate Loans", "name_uz": "Uzoq muddatli korporativ kreditlar"},
        {"code": "132", "group_id": group_map["13"], "name_en": "Long-term SME Loans", "name_uz": "Uzoq muddatli KOB kreditlari"},
        {"code": "133", "group_id": group_map["13"], "name_en": "Project Finance", "name_uz": "Loyiha moliyalashtirish"},
        
        # 14x - Consumer Loans
        {"code": "141", "group_id": group_map["14"], "name_en": "Consumer Loans - Secured", "name_uz": "Iste'mol kreditlari - Ta'minlangan"},
        {"code": "142", "group_id": group_map["14"], "name_en": "Consumer Loans - Unsecured", "name_uz": "Iste'mol kreditlari - Ta'minlanmagan"},
        {"code": "143", "group_id": group_map["14"], "name_en": "Credit Cards", "name_uz": "Kredit kartalari"},
        {"code": "144", "group_id": group_map["14"], "name_en": "Auto Loans", "name_uz": "Avtokredit"},
        
        # 15x - Mortgage
        {"code": "151", "group_id": group_map["15"], "name_en": "Residential Mortgage", "name_uz": "Uy-joy ipotekasi"},
        {"code": "152", "group_id": group_map["15"], "name_en": "Commercial Mortgage", "name_uz": "Tijorat ipotekasi"},
        
        # 16x - Due from Banks
        {"code": "161", "group_id": group_map["16"], "name_en": "Nostro Accounts", "name_uz": "Nostro hisoblar"},
        {"code": "162", "group_id": group_map["16"], "name_en": "Interbank Placements", "name_uz": "Banklararo depozitlar"},
        {"code": "163", "group_id": group_map["16"], "name_en": "Interbank Loans", "name_uz": "Banklararo kreditlar"},
        
        # 17x - Securities
        {"code": "171", "group_id": group_map["17"], "name_en": "Government Bonds", "name_uz": "Davlat obligatsiyalari"},
        {"code": "172", "group_id": group_map["17"], "name_en": "Corporate Bonds", "name_uz": "Korporativ obligatsiyalar"},
        {"code": "173", "group_id": group_map["17"], "name_en": "Equity Investments", "name_uz": "Aksiyalarga investitsiyalar"},
        
        # 18x - Fixed Assets
        {"code": "181", "group_id": group_map["18"], "name_en": "Buildings", "name_uz": "Binolar"},
        {"code": "182", "group_id": group_map["18"], "name_en": "Equipment", "name_uz": "Jihozlar"},
        {"code": "183", "group_id": group_map["18"], "name_en": "IT Equipment", "name_uz": "IT jihozlari"},
        {"code": "184", "group_id": group_map["18"], "name_en": "Vehicles", "name_uz": "Transport vositalari"},
        {"code": "185", "group_id": group_map["18"], "name_en": "Intangible Assets", "name_uz": "Nomoddiy aktivlar"},
        
        # 20x - Deposits
        {"code": "201", "group_id": group_map["20"], "name_en": "Current Accounts - Corporate", "name_uz": "Joriy hisoblar - Korporativ"},
        {"code": "202", "group_id": group_map["20"], "name_en": "Current Accounts - Retail", "name_uz": "Joriy hisoblar - Chakana"},
        {"code": "203", "group_id": group_map["20"], "name_en": "Savings Deposits", "name_uz": "Jamg'arma depozitlari"},
        {"code": "204", "group_id": group_map["20"], "name_en": "Term Deposits - Corporate", "name_uz": "Muddatli depozitlar - Korporativ"},
        {"code": "205", "group_id": group_map["20"], "name_en": "Term Deposits - Retail", "name_uz": "Muddatli depozitlar - Chakana"},
        {"code": "206", "group_id": group_map["20"], "name_en": "Government Deposits", "name_uz": "Davlat depozitlari"},
        
        # 21x - Due to Central Bank
        {"code": "211", "group_id": group_map["21"], "name_en": "CB Repo", "name_uz": "MB Repo"},
        {"code": "212", "group_id": group_map["21"], "name_en": "CB Loans", "name_uz": "MB Kreditlari"},
        
        # 22x - Due to Banks
        {"code": "221", "group_id": group_map["22"], "name_en": "Loro Accounts", "name_uz": "Loro hisoblar"},
        {"code": "222", "group_id": group_map["22"], "name_en": "Interbank Borrowings", "name_uz": "Banklararo qarzlar"},
        
        # 23x - Debt Securities
        {"code": "231", "group_id": group_map["23"], "name_en": "Bonds Issued", "name_uz": "Chiqarilgan obligatsiyalar"},
        {"code": "232", "group_id": group_map["23"], "name_en": "Certificates of Deposit", "name_uz": "Depozit sertifikatlari"},
        
        # 24x - IFI Borrowings
        {"code": "241", "group_id": group_map["24"], "name_en": "IFI Credit Lines", "name_uz": "XMT kredit liniyalari"},
        {"code": "242", "group_id": group_map["24"], "name_en": "Subordinated Debt", "name_uz": "Subordinatsiyalangan qarz"},
        
        # 30x - Share Capital
        {"code": "301", "group_id": group_map["30"], "name_en": "Ordinary Shares", "name_uz": "Oddiy aksiyalar"},
        {"code": "302", "group_id": group_map["30"], "name_en": "Preference Shares", "name_uz": "Imtiyozli aksiyalar"},
        {"code": "303", "group_id": group_map["30"], "name_en": "Share Premium", "name_uz": "Aksiya mukofoti"},
        
        # 31x - Reserves
        {"code": "311", "group_id": group_map["31"], "name_en": "Legal Reserve", "name_uz": "Qonuniy zaxira"},
        {"code": "312", "group_id": group_map["31"], "name_en": "Revaluation Reserve", "name_uz": "Qayta baholash zaxirasi"},
        {"code": "313", "group_id": group_map["31"], "name_en": "FX Translation Reserve", "name_uz": "Valyuta farqi zaxirasi"},
        
        # 32x - Retained Earnings
        {"code": "321", "group_id": group_map["32"], "name_en": "Prior Year Retained Earnings", "name_uz": "O'tgan yil taqsimlanmagan foydasi"},
        {"code": "322", "group_id": group_map["32"], "name_en": "Current Year Profit/Loss", "name_uz": "Joriy yil foyda/zarari"},
        
        # 40x - Interest Income from Loans
        {"code": "401", "group_id": group_map["40"], "name_en": "Interest - Corporate Loans", "name_uz": "Foiz - Korporativ kreditlar"},
        {"code": "402", "group_id": group_map["40"], "name_en": "Interest - SME Loans", "name_uz": "Foiz - KOB kreditlari"},
        {"code": "403", "group_id": group_map["40"], "name_en": "Interest - Consumer Loans", "name_uz": "Foiz - Iste'mol kreditlari"},
        {"code": "404", "group_id": group_map["40"], "name_en": "Interest - Mortgage", "name_uz": "Foiz - Ipoteka"},
        
        # 41x - Interest Income from Securities
        {"code": "411", "group_id": group_map["41"], "name_en": "Interest - Government Securities", "name_uz": "Foiz - Davlat qimmatli qog'ozlari"},
        {"code": "412", "group_id": group_map["41"], "name_en": "Interest - Corporate Securities", "name_uz": "Foiz - Korporativ qimmatli qog'ozlar"},
        
        # 42x - Interest Income from Banks
        {"code": "421", "group_id": group_map["42"], "name_en": "Interest - Interbank Placements", "name_uz": "Foiz - Banklararo depozitlar"},
        {"code": "422", "group_id": group_map["42"], "name_en": "Interest - Central Bank", "name_uz": "Foiz - Markaziy bank"},
        
        # 43x - Fee Income
        {"code": "431", "group_id": group_map["43"], "name_en": "Loan Origination Fees", "name_uz": "Kredit berish komissiyasi"},
        {"code": "432", "group_id": group_map["43"], "name_en": "Account Service Fees", "name_uz": "Hisob xizmati komissiyasi"},
        {"code": "433", "group_id": group_map["43"], "name_en": "Card Fees", "name_uz": "Karta komissiyasi"},
        {"code": "434", "group_id": group_map["43"], "name_en": "Transfer Fees", "name_uz": "O'tkazma komissiyasi"},
        
        # 44x - FX Income
        {"code": "441", "group_id": group_map["44"], "name_en": "FX Trading Gains", "name_uz": "Valyuta savdosi daromadi"},
        {"code": "442", "group_id": group_map["44"], "name_en": "FX Revaluation Gains", "name_uz": "Valyuta qayta baholash daromadi"},
        
        # 50x - Interest Expense on Deposits
        {"code": "501", "group_id": group_map["50"], "name_en": "Interest - Current Accounts", "name_uz": "Foiz - Joriy hisoblar"},
        {"code": "502", "group_id": group_map["50"], "name_en": "Interest - Savings", "name_uz": "Foiz - Jamg'arma"},
        {"code": "503", "group_id": group_map["50"], "name_en": "Interest - Term Deposits", "name_uz": "Foiz - Muddatli depozitlar"},
        
        # 51x - Interest Expense on Borrowings
        {"code": "511", "group_id": group_map["51"], "name_en": "Interest - CB Borrowings", "name_uz": "Foiz - MB qarzlari"},
        {"code": "512", "group_id": group_map["51"], "name_en": "Interest - Interbank", "name_uz": "Foiz - Banklararo"},
        {"code": "513", "group_id": group_map["51"], "name_en": "Interest - IFI Loans", "name_uz": "Foiz - XMT kreditlari"},
        {"code": "514", "group_id": group_map["51"], "name_en": "Interest - Bonds", "name_uz": "Foiz - Obligatsiyalar"},
        
        # 53x - Personnel
        {"code": "531", "group_id": group_map["53"], "name_en": "Salaries", "name_uz": "Ish haqi"},
        {"code": "532", "group_id": group_map["53"], "name_en": "Bonuses", "name_uz": "Mukofotlar"},
        {"code": "533", "group_id": group_map["53"], "name_en": "Social Contributions", "name_uz": "Ijtimoiy to'lovlar"},
        {"code": "534", "group_id": group_map["53"], "name_en": "Training", "name_uz": "O'qitish xarajatlari"},
        
        # 54x - Administrative
        {"code": "541", "group_id": group_map["54"], "name_en": "Rent", "name_uz": "Ijara"},
        {"code": "542", "group_id": group_map["54"], "name_en": "Utilities", "name_uz": "Kommunal xizmatlar"},
        {"code": "543", "group_id": group_map["54"], "name_en": "IT Expenses", "name_uz": "IT xarajatlari"},
        {"code": "544", "group_id": group_map["54"], "name_en": "Professional Services", "name_uz": "Professional xizmatlar"},
        {"code": "545", "group_id": group_map["54"], "name_en": "Marketing", "name_uz": "Marketing"},
        
        # 55x - Depreciation
        {"code": "551", "group_id": group_map["55"], "name_en": "Depreciation - Buildings", "name_uz": "Amortizatsiya - Binolar"},
        {"code": "552", "group_id": group_map["55"], "name_en": "Depreciation - Equipment", "name_uz": "Amortizatsiya - Jihozlar"},
        {"code": "553", "group_id": group_map["55"], "name_en": "Amortization - Intangibles", "name_uz": "Amortizatsiya - Nomoddiy aktivlar"},
        
        # 56x - Provisions
        {"code": "561", "group_id": group_map["56"], "name_en": "Provision - Corporate Loans", "name_uz": "Zaxira - Korporativ kreditlar"},
        {"code": "562", "group_id": group_map["56"], "name_en": "Provision - SME Loans", "name_uz": "Zaxira - KOB kreditlari"},
        {"code": "563", "group_id": group_map["56"], "name_en": "Provision - Consumer Loans", "name_uz": "Zaxira - Iste'mol kreditlari"},
        {"code": "564", "group_id": group_map["56"], "name_en": "Provision - Mortgage", "name_uz": "Zaxira - Ipoteka"},
        {"code": "565", "group_id": group_map["56"], "name_en": "Provision - Other Assets", "name_uz": "Zaxira - Boshqa aktivlar"},
    ]
    
    created = 0
    for cat_data in categories:
        existing = db.query(AccountCategory).filter(AccountCategory.code == cat_data["code"]).first()
        if not existing:
            db.add(AccountCategory(**cat_data))
            created += 1
    
    db.commit()
    print(f"Created {created} account categories")
    return created


def seed_accounts(db):
    """Seed sample 5-digit accounts"""
    
    category_map = {c.code: c.id for c in db.query(AccountCategory).all()}
    
    accounts = [
        # Cash accounts
        {"code": "10101", "category_id": category_map["101"], "name_en": "Cash in Vault - UZS", "name_uz": "Kassadagi naqd pul - UZS"},
        {"code": "10201", "category_id": category_map["102"], "name_en": "Cash in Vault - USD", "name_uz": "Kassadagi naqd pul - USD"},
        {"code": "10202", "category_id": category_map["102"], "name_en": "Cash in Vault - EUR", "name_uz": "Kassadagi naqd pul - EUR"},
        
        # Central Bank
        {"code": "11101", "category_id": category_map["111"], "name_en": "Required Reserves - UZS", "name_uz": "Majburiy zaxiralar - UZS"},
        {"code": "11201", "category_id": category_map["112"], "name_en": "Required Reserves - USD", "name_uz": "Majburiy zaxiralar - USD"},
        
        # Corporate Loans
        {"code": "12101", "category_id": category_map["121"], "name_en": "Short-term Corporate Loans - UZS", "name_uz": "Qisqa muddatli korporativ kreditlar - UZS"},
        {"code": "12102", "category_id": category_map["121"], "name_en": "Short-term Corporate Loans - USD", "name_uz": "Qisqa muddatli korporativ kreditlar - USD"},
        {"code": "12201", "category_id": category_map["122"], "name_en": "Short-term SME Loans - UZS", "name_uz": "Qisqa muddatli KOB kreditlari - UZS"},
        
        # Long-term Loans
        {"code": "13101", "category_id": category_map["131"], "name_en": "Long-term Corporate Loans - UZS", "name_uz": "Uzoq muddatli korporativ kreditlar - UZS"},
        {"code": "13102", "category_id": category_map["131"], "name_en": "Long-term Corporate Loans - USD", "name_uz": "Uzoq muddatli korporativ kreditlar - USD"},
        
        # Consumer Loans
        {"code": "14101", "category_id": category_map["141"], "name_en": "Consumer Loans - Secured - UZS", "name_uz": "Iste'mol kreditlari - Ta'minlangan - UZS"},
        {"code": "14201", "category_id": category_map["142"], "name_en": "Consumer Loans - Unsecured - UZS", "name_uz": "Iste'mol kreditlari - Ta'minlanmagan - UZS"},
        {"code": "14301", "category_id": category_map["143"], "name_en": "Credit Card Receivables - UZS", "name_uz": "Kredit karta qoldiqlari - UZS"},
        
        # Mortgage
        {"code": "15101", "category_id": category_map["151"], "name_en": "Residential Mortgage - UZS", "name_uz": "Uy-joy ipotekasi - UZS"},
        {"code": "15201", "category_id": category_map["152"], "name_en": "Commercial Mortgage - UZS", "name_uz": "Tijorat ipotekasi - UZS"},
        
        # Deposits
        {"code": "20101", "category_id": category_map["201"], "name_en": "Current Accounts - Corporate - UZS", "name_uz": "Joriy hisoblar - Korporativ - UZS"},
        {"code": "20102", "category_id": category_map["201"], "name_en": "Current Accounts - Corporate - USD", "name_uz": "Joriy hisoblar - Korporativ - USD"},
        {"code": "20201", "category_id": category_map["202"], "name_en": "Current Accounts - Retail - UZS", "name_uz": "Joriy hisoblar - Chakana - UZS"},
        {"code": "20301", "category_id": category_map["203"], "name_en": "Savings Deposits - UZS", "name_uz": "Jamg'arma depozitlari - UZS"},
        {"code": "20401", "category_id": category_map["204"], "name_en": "Term Deposits - Corporate - UZS", "name_uz": "Muddatli depozitlar - Korporativ - UZS"},
        {"code": "20501", "category_id": category_map["205"], "name_en": "Term Deposits - Retail - UZS", "name_uz": "Muddatli depozitlar - Chakana - UZS"},
        
        # Equity
        {"code": "30101", "category_id": category_map["301"], "name_en": "Ordinary Shares", "name_uz": "Oddiy aksiyalar"},
        {"code": "31101", "category_id": category_map["311"], "name_en": "Legal Reserve Fund", "name_uz": "Qonuniy zaxira fondi"},
        {"code": "32101", "category_id": category_map["321"], "name_en": "Prior Year Retained Earnings", "name_uz": "O'tgan yil taqsimlanmagan foydasi"},
        {"code": "32201", "category_id": category_map["322"], "name_en": "Current Year Net Income", "name_uz": "Joriy yil sof foydasi"},
        
        # Interest Income
        {"code": "40101", "category_id": category_map["401"], "name_en": "Interest Income - Corporate Loans - UZS", "name_uz": "Foiz daromadi - Korporativ kreditlar - UZS"},
        {"code": "40102", "category_id": category_map["401"], "name_en": "Interest Income - Corporate Loans - USD", "name_uz": "Foiz daromadi - Korporativ kreditlar - USD"},
        {"code": "40201", "category_id": category_map["402"], "name_en": "Interest Income - SME Loans - UZS", "name_uz": "Foiz daromadi - KOB kreditlari - UZS"},
        {"code": "40301", "category_id": category_map["403"], "name_en": "Interest Income - Consumer Loans - UZS", "name_uz": "Foiz daromadi - Iste'mol kreditlari - UZS"},
        {"code": "40401", "category_id": category_map["404"], "name_en": "Interest Income - Mortgage - UZS", "name_uz": "Foiz daromadi - Ipoteka - UZS"},
        
        # Fee Income
        {"code": "43101", "category_id": category_map["431"], "name_en": "Loan Origination Fees", "name_uz": "Kredit berish komissiyasi"},
        {"code": "43201", "category_id": category_map["432"], "name_en": "Account Maintenance Fees", "name_uz": "Hisob xizmati komissiyasi"},
        {"code": "43301", "category_id": category_map["433"], "name_en": "Card Annual Fees", "name_uz": "Karta yillik to'lovi"},
        
        # Interest Expense
        {"code": "50101", "category_id": category_map["501"], "name_en": "Interest Expense - Current Accounts - UZS", "name_uz": "Foiz xarajati - Joriy hisoblar - UZS"},
        {"code": "50201", "category_id": category_map["502"], "name_en": "Interest Expense - Savings - UZS", "name_uz": "Foiz xarajati - Jamg'arma - UZS"},
        {"code": "50301", "category_id": category_map["503"], "name_en": "Interest Expense - Term Deposits - UZS", "name_uz": "Foiz xarajati - Muddatli depozitlar - UZS"},
        
        # Personnel
        {"code": "53101", "category_id": category_map["531"], "name_en": "Base Salaries", "name_uz": "Asosiy ish haqi"},
        {"code": "53201", "category_id": category_map["532"], "name_en": "Performance Bonuses", "name_uz": "Natijaga asoslangan mukofotlar"},
        {"code": "53301", "category_id": category_map["533"], "name_en": "Social Security Contributions", "name_uz": "Ijtimoiy sug'urta to'lovlari"},
        
        # Administrative
        {"code": "54101", "category_id": category_map["541"], "name_en": "Office Rent", "name_uz": "Ofis ijarasi"},
        {"code": "54201", "category_id": category_map["542"], "name_en": "Electricity and Utilities", "name_uz": "Elektr va kommunal xizmatlar"},
        {"code": "54301", "category_id": category_map["543"], "name_en": "Software Licenses", "name_uz": "Dasturiy ta'minot litsenziyalari"},
        
        # Provisions
        {"code": "56101", "category_id": category_map["561"], "name_en": "Provision Expense - Corporate Loans", "name_uz": "Zaxira xarajati - Korporativ kreditlar"},
        {"code": "56201", "category_id": category_map["562"], "name_en": "Provision Expense - SME Loans", "name_uz": "Zaxira xarajati - KOB kreditlari"},
        {"code": "56301", "category_id": category_map["563"], "name_en": "Provision Expense - Consumer Loans", "name_uz": "Zaxira xarajati - Iste'mol kreditlari"},
    ]
    
    created = 0
    for acc_data in accounts:
        existing = db.query(Account).filter(Account.code == acc_data["code"]).first()
        if not existing:
            db.add(Account(**acc_data))
            created += 1
    
    db.commit()
    print(f"Created {created} accounts")
    return created


def seed_business_units(db):
    """Seed business units"""
    
    units = [
        {"code": "CORP", "name_en": "Corporate Banking", "name_uz": "Korporativ bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 1},
        {"code": "RETAIL", "name_en": "Retail Banking", "name_uz": "Chakana bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 2},
        {"code": "SME", "name_en": "SME Banking", "name_uz": "KOB bank", "unit_type": BusinessUnitType.REVENUE_CENTER, "display_order": 3},
        {"code": "TREASURY", "name_en": "Treasury", "name_uz": "G'aznachilik", "unit_type": BusinessUnitType.PROFIT_CENTER, "display_order": 4},
        {"code": "RISK", "name_en": "Risk Management", "name_uz": "Risk boshqaruvi", "unit_type": BusinessUnitType.SUPPORT_CENTER, "display_order": 5},
        {"code": "HR", "name_en": "Human Resources", "name_uz": "Kadrlar bo'limi", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 6},
        {"code": "IT", "name_en": "Information Technology", "name_uz": "Axborot texnologiyalari", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 7},
        {"code": "OPS", "name_en": "Operations", "name_uz": "Operatsiyalar", "unit_type": BusinessUnitType.SUPPORT_CENTER, "display_order": 8},
        {"code": "ADMIN", "name_en": "Administration", "name_uz": "Ma'muriyat", "unit_type": BusinessUnitType.COST_CENTER, "display_order": 9},
        {"code": "FINANCE", "name_en": "Finance & Accounting", "name_uz": "Moliya va buxgalteriya", "unit_type": BusinessUnitType.SUPPORT_CENTER, "display_order": 10},
    ]
    
    created = 0
    for unit_data in units:
        existing = db.query(BusinessUnit).filter(BusinessUnit.code == unit_data["code"]).first()
        if not existing:
            db.add(BusinessUnit(**unit_data))
            created += 1
    
    db.commit()
    print(f"Created {created} business units")
    return created


def seed_account_mappings(db):
    """Seed account mappings (Balance -> P&L links)"""
    
    mappings = [
        # Loans -> Interest Income
        {"balance_account_code": "121", "pnl_account_code": "401", "mapping_type": "interest_income", "description": "Corporate loans -> Interest income"},
        {"balance_account_code": "122", "pnl_account_code": "402", "mapping_type": "interest_income", "description": "SME loans -> Interest income"},
        {"balance_account_code": "141", "pnl_account_code": "403", "mapping_type": "interest_income", "description": "Consumer loans -> Interest income"},
        {"balance_account_code": "151", "pnl_account_code": "404", "mapping_type": "interest_income", "description": "Mortgage -> Interest income"},
        
        # Loans -> Provisions
        {"balance_account_code": "121", "pnl_account_code": "561", "mapping_type": "provision", "description": "Corporate loans -> Provision expense"},
        {"balance_account_code": "122", "pnl_account_code": "562", "mapping_type": "provision", "description": "SME loans -> Provision expense"},
        {"balance_account_code": "141", "pnl_account_code": "563", "mapping_type": "provision", "description": "Consumer loans -> Provision expense"},
        {"balance_account_code": "151", "pnl_account_code": "564", "mapping_type": "provision", "description": "Mortgage -> Provision expense"},
        
        # Deposits -> Interest Expense
        {"balance_account_code": "201", "pnl_account_code": "501", "mapping_type": "interest_expense", "description": "Current accounts -> Interest expense"},
        {"balance_account_code": "203", "pnl_account_code": "502", "mapping_type": "interest_expense", "description": "Savings -> Interest expense"},
        {"balance_account_code": "204", "pnl_account_code": "503", "mapping_type": "interest_expense", "description": "Term deposits -> Interest expense"},
        {"balance_account_code": "205", "pnl_account_code": "503", "mapping_type": "interest_expense", "description": "Term deposits retail -> Interest expense"},
    ]
    
    created = 0
    for map_data in mappings:
        existing = db.query(AccountMapping).filter(
            AccountMapping.balance_account_code == map_data["balance_account_code"],
            AccountMapping.pnl_account_code == map_data["pnl_account_code"]
        ).first()
        if not existing:
            db.add(AccountMapping(**map_data))
            created += 1
    
    db.commit()
    print(f"Created {created} account mappings")
    return created


def seed_responsibilities(db):
    """Seed account responsibilities (which unit is responsible for which accounts)"""
    
    unit_map = {u.code: u.id for u in db.query(BusinessUnit).all()}
    
    account_unit_map = {
        # Corporate Banking
        "12101": ["CORP"],  # Short-term corporate loans
        "12102": ["CORP"],
        "13101": ["CORP"],  # Long-term corporate loans
        "13102": ["CORP"],
        "20101": ["CORP"],  # Corporate current accounts
        "20102": ["CORP"],
        "20401": ["CORP"],  # Corporate term deposits
        "40101": ["CORP"],  # Interest income - corporate
        "40102": ["CORP"],
        "56101": ["RISK"],  # Provision - corporate (Risk manages)
        
        # SME Banking
        "12201": ["SME"],  # SME loans
        "40201": ["SME"],  # Interest income - SME
        "56201": ["RISK"],  # Provision - SME
        
        # Retail Banking
        "14101": ["RETAIL"],  # Consumer loans
        "14201": ["RETAIL"],
        "14301": ["RETAIL"],  # Credit cards
        "15101": ["RETAIL"],  # Mortgage
        "20201": ["RETAIL"],  # Retail current accounts
        "20301": ["RETAIL"],  # Savings
        "20501": ["RETAIL"],  # Retail term deposits
        "40301": ["RETAIL"],  # Interest income - consumer
        "40401": ["RETAIL"],  # Interest income - mortgage
        "56301": ["RISK"],  # Provision - consumer
        
        # Treasury
        "10101": ["TREASURY"],  # Cash
        "10201": ["TREASURY"],
        "10202": ["TREASURY"],
        "11101": ["TREASURY"],  # CB reserves
        "11201": ["TREASURY"],
        
        # HR
        "53101": ["HR"],  # Salaries
        "53201": ["HR"],  # Bonuses
        "53301": ["HR"],  # Social contributions
        
        # IT
        "54301": ["IT"],  # Software licenses
        
        # Admin
        "54101": ["ADMIN"],  # Rent
        "54201": ["ADMIN"],  # Utilities
        
        # Finance
        "30101": ["FINANCE"],  # Share capital
        "31101": ["FINANCE"],  # Reserves
        "32101": ["FINANCE"],  # Retained earnings
        "32201": ["FINANCE"],
    }
    
    created = 0
    for account_code, unit_codes in account_unit_map.items():
        account = db.query(Account).filter(Account.code == account_code).first()
        if not account:
            continue
            
        for i, unit_code in enumerate(unit_codes):
            if unit_code not in unit_map:
                continue
                
            existing = db.query(AccountResponsibility).filter(
                AccountResponsibility.account_id == account.id,
                AccountResponsibility.business_unit_id == unit_map[unit_code]
            ).first()
            
            if not existing:
                resp = AccountResponsibility(
                    account_id=account.id,
                    business_unit_id=unit_map[unit_code],
                    is_primary=(i == 0),
                    can_budget=True,
                    can_view=True
                )
                db.add(resp)
                created += 1
    
    db.commit()
    print(f"Created {created} account responsibilities")
    return created


def main():
    """Run all seed functions"""
    print("=" * 50)
    print("Seeding Uzbek Banking COA Data")
    print("=" * 50)
    
    db = SessionLocal()
    
    try:
        seed_account_classes(db)
        seed_account_groups(db)
        seed_account_categories(db)
        seed_accounts(db)
        seed_business_units(db)
        seed_account_mappings(db)
        seed_responsibilities(db)
        
        print("=" * 50)
        print("COA Seeding Complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
