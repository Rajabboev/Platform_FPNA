# backend/app/services/excel_service.py
"""
Excel processing service
"""

import pandas as pd
import openpyxl
from typing import Dict, List, Any
from datetime import datetime
import os


class ExcelProcessor:
    """Process Excel files for budget upload"""
    
    @staticmethod
    def parse_budget_excel(file_path: str) -> Dict[str, Any]:
        """
        Parse Excel file and extract budget data
        
        Expected Excel format:
        Sheet 1: Header
            - Fiscal Year
            - Department
            - Branch
            - Description
            - Currency
        
        Sheet 2: LineItems
            - Account Code
            - Account Name
            - Category
            - Month
            - Quarter
            - Year
            - Amount
            - Quantity (optional)
            - Unit Price (optional)
            - Notes (optional)
        """
        
        try:
            # Read Excel file
            xl_file = pd.ExcelFile(file_path)
            
            # Check required sheets
            if 'Header' not in xl_file.sheet_names or 'LineItems' not in xl_file.sheet_names:
                raise ValueError("Excel must contain 'Header' and 'LineItems' sheets")
            
            # Parse Header sheet
            header_df = pd.read_excel(file_path, sheet_name='Header')
            
            # Extract header info (key-value pairs)
            header_data = {}
            for _, row in header_df.iterrows():
                if 'Field' in row and 'Value' in row:
                    header_data[str(row['Field']).strip()] = row['Value']
            
            # Parse LineItems sheet
            items_df = pd.read_excel(file_path, sheet_name='LineItems')
            
            # Clean column names
            items_df.columns = items_df.columns.str.strip()
            
            # Convert to list of dictionaries
            line_items = []
            for _, row in items_df.iterrows():
                item = {
                    'account_code': str(row.get('Account Code', '')).strip(),
                    'account_name': str(row.get('Account Name', '')).strip(),
                    'category': str(row.get('Category', '')).strip() if pd.notna(row.get('Category')) else None,
                    'month': int(row.get('Month')) if pd.notna(row.get('Month')) else None,
                    'quarter': int(row.get('Quarter')) if pd.notna(row.get('Quarter')) else None,
                    'year': int(row.get('Year')) if pd.notna(row.get('Year')) else None,
                    'amount': float(row.get('Amount', 0)),
                    'quantity': float(row.get('Quantity')) if pd.notna(row.get('Quantity')) else None,
                    'unit_price': float(row.get('Unit Price')) if pd.notna(row.get('Unit Price')) else None,
                    'notes': str(row.get('Notes', '')).strip() if pd.notna(row.get('Notes')) else None,
                }
                
                # Validate required fields
                if not item['account_code'] or not item['account_name']:
                    continue  # Skip invalid rows
                
                line_items.append(item)
            
            if not line_items:
                raise ValueError("No valid line items found in Excel file")
            
            # Calculate total amount
            total_amount = sum(item['amount'] for item in line_items)
            
            # Build result
            result = {
                'header': {
                    'fiscal_year': int(header_data.get('Fiscal Year', datetime.now().year)),
                    'department': str(header_data.get('Department', '')),
                    'branch': str(header_data.get('Branch', '')),
                    'description': str(header_data.get('Description', '')),
                    'currency': str(header_data.get('Currency', 'USD')),
                },
                'line_items': line_items,
                'total_amount': total_amount,
                'summary': {
                    'total_items': len(line_items),
                    'total_amount': total_amount,
                    'categories': list(set(item['category'] for item in line_items if item['category']))
                }
            }
            
            return result
            
        except Exception as e:
            raise ValueError(f"Error parsing Excel file: {str(e)}")
    
    @staticmethod
    def create_template(file_path: str):
        """Create Excel template for budget upload"""
        
        # Create workbook
        wb = openpyxl.Workbook()
        
        # Create Header sheet
        ws_header = wb.active
        ws_header.title = "Header"
        ws_header['A1'] = "Field"
        ws_header['B1'] = "Value"
        ws_header['A2'] = "Fiscal Year"
        ws_header['B2'] = 2025
        ws_header['A3'] = "Department"
        ws_header['B3'] = "Finance"
        ws_header['A4'] = "Branch"
        ws_header['B4'] = "Head Office"
        ws_header['A5'] = "Description"
        ws_header['B5'] = "Annual Budget 2025"
        ws_header['A6'] = "Currency"
        ws_header['B6'] = "USD"
        
        # Style header sheet
        for cell in ws_header[1]:
            cell.font = openpyxl.styles.Font(bold=True)
        
        # Create LineItems sheet
        ws_items = wb.create_sheet("LineItems")
        headers = [
            "Account Code", "Account Name", "Category", "Month", 
            "Quarter", "Year", "Amount", "Quantity", "Unit Price", "Notes"
        ]
        ws_items.append(headers)
        
        # Add sample data
        sample_data = [
            ["4000", "Revenue - Sales", "Revenue", 1, 1, 2025, 100000, 500, 200, "Q1 Sales Target"],
            ["4010", "Revenue - Services", "Revenue", 1, 1, 2025, 50000, None, None, "Consulting"],
            ["5000", "Cost of Goods Sold", "COGS", 1, 1, 2025, 40000, 500, 80, "Product Costs"],
            ["6000", "Salaries", "Operating Expenses", 1, 1, 2025, 60000, None, None, "Staff Salaries"],
            ["6100", "Rent", "Operating Expenses", 1, 1, 2025, 15000, None, None, "Office Rent"],
        ]
        
        for row in sample_data:
            ws_items.append(row)
        
        # Style LineItems sheet
        for cell in ws_items[1]:
            cell.font = openpyxl.styles.Font(bold=True)
            cell.fill = openpyxl.styles.PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        
        # Adjust column widths
        for ws in [ws_header, ws_items]:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
        
        # Save workbook
        wb.save(file_path)
        
        return file_path