"""Base class for data source extractors"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class DataSourceExtractor(ABC):
    """Abstract base class for all data source extractors.
    
    All extractors must implement:
    - extract(): Fetch data from the source and return as DataFrame
    - get_columns(): Return list of available columns
    - test_connection(): Verify the source is accessible
    """
    
    @abstractmethod
    def extract(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Extract data from the source.
        
        Args:
            limit: Optional limit on number of rows to extract (for preview)
            
        Returns:
            DataFrame containing the extracted data
        """
        pass
    
    @abstractmethod
    def get_columns(self) -> List[Dict[str, Any]]:
        """Get list of available columns from the source.
        
        Returns:
            List of dicts with column info: [{"name": str, "type": str}, ...]
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """Test if the source is accessible.
        
        Returns:
            Dict with "success": bool and "message": str
        """
        pass
    
    def preview(self, rows: int = 10) -> Dict[str, Any]:
        """Preview data from the source.
        
        Args:
            rows: Number of rows to preview
            
        Returns:
            Dict with "columns", "data", and "total_rows" (if available)
        """
        df = self.extract(limit=rows)
        return {
            "columns": [{"name": col, "type": str(df[col].dtype)} for col in df.columns],
            "data": df.to_dict(orient="records"),
            "row_count": len(df)
        }


class ExtractionError(Exception):
    """Raised when data extraction fails"""
    pass


class ConnectionError(Exception):
    """Raised when connection to source fails"""
    pass
