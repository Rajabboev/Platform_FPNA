"""File-based data source extractors for Excel and CSV files"""
import pandas as pd
import io
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from .base import DataSourceExtractor, ExtractionError


class ExcelExtractor(DataSourceExtractor):
    """Extract data from Excel files (.xlsx, .xls)"""
    
    def __init__(
        self,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        sheet_name: Optional[str] = None
    ):
        """Initialize Excel extractor.
        
        Args:
            file_path: Path to Excel file on disk
            file_content: Raw bytes of Excel file (for uploaded files)
            sheet_name: Specific sheet to extract (None = first sheet)
        """
        if not file_path and not file_content:
            raise ValueError("Either file_path or file_content must be provided")
        
        self.file_path = file_path
        self.file_content = file_content
        self.sheet_name = sheet_name
        self._excel_file = None
        self._df = None
    
    def _get_excel_source(self) -> Union[str, io.BytesIO]:
        """Get the source for pandas to read from"""
        if self.file_content:
            return io.BytesIO(self.file_content)
        return self.file_path
    
    def _load_excel(self):
        """Load Excel file if not already loaded"""
        if self._excel_file is None:
            try:
                self._excel_file = pd.ExcelFile(self._get_excel_source())
            except Exception as e:
                raise ExtractionError(f"Failed to open Excel file: {str(e)}")
    
    def get_sheet_names(self) -> List[str]:
        """Get list of available sheet names"""
        self._load_excel()
        return self._excel_file.sheet_names
    
    def extract(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Extract data from Excel file.
        
        Args:
            limit: Optional limit on rows to extract
            
        Returns:
            DataFrame with extracted data
        """
        self._load_excel()
        
        try:
            sheet = self.sheet_name if self.sheet_name else 0
            
            if limit:
                df = pd.read_excel(
                    self._get_excel_source(),
                    sheet_name=sheet,
                    nrows=limit
                )
            else:
                df = pd.read_excel(
                    self._get_excel_source(),
                    sheet_name=sheet
                )
            
            df.columns = df.columns.astype(str).str.strip()
            self._df = df
            return df
            
        except Exception as e:
            raise ExtractionError(f"Failed to extract data from Excel: {str(e)}")
    
    def get_columns(self) -> List[Dict[str, Any]]:
        """Get column information from Excel file"""
        if self._df is None:
            self.extract(limit=1)
        
        columns = []
        for col in self._df.columns:
            dtype = str(self._df[col].dtype)
            columns.append({
                "name": col,
                "type": dtype
            })
        return columns
    
    def test_connection(self) -> Dict[str, Any]:
        """Test if Excel file is readable"""
        try:
            self._load_excel()
            sheets = self.get_sheet_names()
            return {
                "success": True,
                "message": f"Excel file readable with {len(sheets)} sheet(s): {', '.join(sheets)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }


class CSVExtractor(DataSourceExtractor):
    """Extract data from CSV files"""
    
    def __init__(
        self,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        delimiter: str = ",",
        encoding: str = "utf-8"
    ):
        """Initialize CSV extractor.
        
        Args:
            file_path: Path to CSV file on disk
            file_content: Raw bytes of CSV file (for uploaded files)
            delimiter: Column delimiter (default: comma)
            encoding: File encoding (default: utf-8)
        """
        if not file_path and not file_content:
            raise ValueError("Either file_path or file_content must be provided")
        
        self.file_path = file_path
        self.file_content = file_content
        self.delimiter = delimiter
        self.encoding = encoding
        self._df = None
    
    def _get_csv_source(self) -> Union[str, io.StringIO]:
        """Get the source for pandas to read from"""
        if self.file_content:
            return io.StringIO(self.file_content.decode(self.encoding))
        return self.file_path
    
    def extract(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Extract data from CSV file.
        
        Args:
            limit: Optional limit on rows to extract
            
        Returns:
            DataFrame with extracted data
        """
        try:
            kwargs = {
                "delimiter": self.delimiter,
                "encoding": self.encoding if self.file_path else None
            }
            
            if limit:
                kwargs["nrows"] = limit
            
            if self.file_content:
                source = io.StringIO(self.file_content.decode(self.encoding))
                del kwargs["encoding"]
            else:
                source = self.file_path
            
            df = pd.read_csv(source, **kwargs)
            df.columns = df.columns.astype(str).str.strip()
            self._df = df
            return df
            
        except Exception as e:
            raise ExtractionError(f"Failed to extract data from CSV: {str(e)}")
    
    def get_columns(self) -> List[Dict[str, Any]]:
        """Get column information from CSV file"""
        if self._df is None:
            self.extract(limit=5)
        
        columns = []
        for col in self._df.columns:
            dtype = str(self._df[col].dtype)
            columns.append({
                "name": col,
                "type": dtype
            })
        return columns
    
    def test_connection(self) -> Dict[str, Any]:
        """Test if CSV file is readable"""
        try:
            df = self.extract(limit=1)
            return {
                "success": True,
                "message": f"CSV file readable with {len(df.columns)} column(s)"
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
    
    def detect_delimiter(self) -> str:
        """Try to auto-detect the delimiter"""
        import csv
        
        if self.file_content:
            sample = self.file_content.decode(self.encoding)[:4096]
        else:
            with open(self.file_path, 'r', encoding=self.encoding) as f:
                sample = f.read(4096)
        
        try:
            dialect = csv.Sniffer().sniff(sample)
            return dialect.delimiter
        except:
            return ","
