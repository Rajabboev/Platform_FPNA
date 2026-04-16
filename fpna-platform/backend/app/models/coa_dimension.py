"""
COA Dimension Model - CBU Chart of Accounts Hierarchy

This model stores the official CBU (Central Bank of Uzbekistan) Chart of Accounts
hierarchy used for regulatory reporting and budgeting.

Hierarchy Levels:
- L1: BS_FLAG (Balance Sheet Class: 1=Assets, 2=Liabilities, 3=Capital, 9=Off-balance)
- L2: BS_GROUP (3-digit group code, e.g., 10100)
- L3: COA_CODE (5-digit account code, e.g., 10101)

Key Groupings:
- fpna_product_* columns: FP&A product taxonomy (derived on import) — primary planning bucket
- P_L categorization: For income statement accounts
- budgeting_groups: optional legacy CBU field (not used for FP&A logic)
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base

    
class COADimension(Base):
    """
    CBU Chart of Accounts Dimension
    Primary key: COA_CODE (5-digit account number)
    """
    __tablename__ = "coa_dimension"

    id = Column(Integer, primary_key=True, index=True)
    
    # Core Identifiers
    coa_code = Column(String(10), unique=True, nullable=False, index=True)
    code = Column(String(10))  # MDS internal code (usually same as coa_code)
    name = Column(String(255))  # MDS reference name
    
    # Balance Sheet Hierarchy - Level 1 (Class)
    bs_flag = Column(Integer, index=True)  # 1=Assets, 2=Liabilities, 3=Capital, 9=Off-balance
    bs_flag_1 = Column(Integer)  # Alternative flag
    bs_name = Column(String(255))  # Class name (e.g., "Активлар")
    bs_flag_1_name = Column(String(255))
    
    # Balance Sheet Hierarchy - Level 2 (Group)
    bs_group = Column(Integer, index=True)  # 3-digit group (e.g., 10100)
    group_name = Column(String(500))  # Group description
    
    # Balance Sheet Hierarchy - Level 3 (Account)
    coa_name = Column(String(1000))  # Full account name
    
    # Regulatory Groupings (CBU/MKB)
    mkb_bs_group_flag = Column(Integer)
    mkb_bs_group = Column(String(255))
    bs_cbu_sub_item_group = Column(Integer)
    bs_cbu_item_name = Column(String(500))
    bs_cbu_sub_item = Column(Integer)
    bs_cbu_sub_item_name = Column(String(500))
    
    # Asset/Liability Classification
    asset_liability_flag_1 = Column(Integer)
    asset_liability_flag_1_name = Column(String(255))
    asset_liability_flag_2 = Column(Integer)
    asset_liability_flag_2_name = Column(String(255))
    
    # Legacy CBU budgeting group (optional Excel column — not used for FP&A planning logic)
    budgeting_groups = Column(Integer, index=True, nullable=True)
    budgeting_groups_name = Column(String(500), nullable=True)

    # FP&A product taxonomy (derived on import; primary bucket for planning & hierarchy)
    fpna_product_key = Column(String(50), nullable=True, index=True)
    fpna_product_label_en = Column(String(500), nullable=True)
    fpna_product_pillar = Column(String(50), nullable=True)
    fpna_display_group = Column(String(1000), nullable=True)
    
    # P&L Classification
    p_l_flag = Column(Integer)
    p_l_flag_name = Column(String(255))  # Interest Income, Non-Interest Income, etc.
    p_l_group = Column(Integer)
    p_l_sub_group = Column(Integer)
    p_l_sub_group_name = Column(String(255))
    p_l_sub_group_name_ru = Column(String(255))
    p_l_sub_group_name_rus = Column(String(255))
    p_l_flag_name_rus = Column(String(255))  # Broad P&L classification
    
    # Metadata
    is_active = Column(Boolean, default=True)
    validation_status = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('ix_coa_dim_bs_flag_group', 'bs_flag', 'bs_group'),
        Index('ix_coa_dim_budgeting', 'budgeting_groups'),
        Index('ix_coa_dim_fpna_product', 'fpna_product_key'),
        Index('ix_coa_dim_pl', 'p_l_flag', 'p_l_sub_group'),
    )

    def __repr__(self):
        return f"<COADimension(coa_code={self.coa_code}, name={self.coa_name[:50] if self.coa_name else ''})>"

    @property
    def is_balance_sheet(self) -> bool:
        """Check if account is a balance sheet account (not off-balance)"""
        return self.bs_flag in (1, 2, 3)
    
    @property
    def is_asset(self) -> bool:
        return self.bs_flag == 1
    
    @property
    def is_liability(self) -> bool:
        return self.bs_flag == 2
    
    @property
    def is_capital(self) -> bool:
        return self.bs_flag == 3
    
    @property
    def is_off_balance(self) -> bool:
        return self.bs_flag == 9
    
    @property
    def has_pl_impact(self) -> bool:
        """Check if account affects P&L (income statement)"""
        return self.p_l_flag is not None


class BudgetingGroup(Base):
    """
    Budgeting Groups lookup table
    Used for FP&A template organization
    """
    __tablename__ = "budgeting_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, unique=True, nullable=False, index=True)
    name_ru = Column(String(500), nullable=False)
    name_en = Column(String(500))
    name_uz = Column(String(500))
    
    # Grouping metadata
    category = Column(String(100))  # ASSET, LIABILITY, CAPITAL, OFF_BALANCE
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Template assignment
    default_template_code = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<BudgetingGroup(id={self.group_id}, name={self.name_ru[:50] if self.name_ru else ''})>"


class BSClass(Base):
    """
    Balance Sheet Classes (Level 1)
    """
    __tablename__ = "bs_classes"
    
    id = Column(Integer, primary_key=True, index=True)
    bs_flag = Column(Integer, unique=True, nullable=False, index=True)
    name_uz = Column(String(255), nullable=False)
    name_ru = Column(String(255))
    name_en = Column(String(255))
    
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<BSClass(bs_flag={self.bs_flag}, name={self.name_uz})>"
