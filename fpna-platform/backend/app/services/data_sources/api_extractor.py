"""REST API data source extractor"""
import pandas as pd
import requests
from typing import List, Dict, Any, Optional
import json

from .base import DataSourceExtractor, ExtractionError, ConnectionError


class APIExtractor(DataSourceExtractor):
    """Extract data from REST API endpoints"""
    
    def __init__(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        auth_type: Optional[str] = None,
        auth_credentials: Optional[Dict[str, str]] = None,
        data_path: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ):
        """Initialize API extractor.
        
        Args:
            url: API endpoint URL
            method: HTTP method (GET, POST)
            headers: Optional HTTP headers
            auth_type: Authentication type (none, basic, bearer, api_key)
            auth_credentials: Auth credentials dict:
                - basic: {"username": str, "password": str}
                - bearer: {"token": str}
                - api_key: {"key": str, "header_name": str} or {"key": str, "param_name": str}
            data_path: JSON path to data array (e.g., "data", "results", "data.items")
            params: URL query parameters
            body: Request body for POST requests
            timeout: Request timeout in seconds
        """
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.auth_type = auth_type
        self.auth_credentials = auth_credentials or {}
        self.data_path = data_path
        self.params = params or {}
        self.body = body
        self.timeout = timeout
        self._response_data = None
        self._df = None
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers including auth"""
        headers = {**self.headers}
        
        if self.auth_type == "bearer":
            token = self.auth_credentials.get("token", "")
            headers["Authorization"] = f"Bearer {token}"
        
        elif self.auth_type == "api_key":
            header_name = self.auth_credentials.get("header_name")
            if header_name:
                headers[header_name] = self.auth_credentials.get("key", "")
        
        if self.method == "POST" and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        return headers
    
    def _build_params(self) -> Dict[str, Any]:
        """Build query parameters including API key if configured"""
        params = {**self.params}
        
        if self.auth_type == "api_key":
            param_name = self.auth_credentials.get("param_name")
            if param_name:
                params[param_name] = self.auth_credentials.get("key", "")
        
        return params
    
    def _get_auth(self):
        """Get requests auth object for basic auth"""
        if self.auth_type == "basic":
            return (
                self.auth_credentials.get("username", ""),
                self.auth_credentials.get("password", "")
            )
        return None
    
    def _extract_data_from_response(self, response_json: Any) -> List[Dict[str, Any]]:
        """Extract data array from JSON response using data_path"""
        if not self.data_path:
            if isinstance(response_json, list):
                return response_json
            elif isinstance(response_json, dict):
                for key in ["data", "results", "items", "records", "rows"]:
                    if key in response_json and isinstance(response_json[key], list):
                        return response_json[key]
                return [response_json]
            return [response_json]
        
        data = response_json
        for key in self.data_path.split("."):
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and key.isdigit():
                data = data[int(key)]
            else:
                raise ExtractionError(f"Cannot navigate to '{key}' in data path '{self.data_path}'")
            
            if data is None:
                raise ExtractionError(f"Data path '{self.data_path}' returned None")
        
        if not isinstance(data, list):
            data = [data]
        
        return data
    
    def _make_request(self) -> requests.Response:
        """Make HTTP request to API"""
        headers = self._build_headers()
        params = self._build_params()
        auth = self._get_auth()
        
        try:
            if self.method == "GET":
                response = requests.get(
                    self.url,
                    headers=headers,
                    params=params,
                    auth=auth,
                    timeout=self.timeout
                )
            elif self.method == "POST":
                response = requests.post(
                    self.url,
                    headers=headers,
                    params=params,
                    auth=auth,
                    json=self.body,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {self.method}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            raise ConnectionError(f"Request timed out after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"Failed to connect to API: {str(e)}")
        except requests.exceptions.HTTPError as e:
            raise ExtractionError(f"API returned error: {e.response.status_code} - {e.response.text[:200]}")
        except Exception as e:
            raise ExtractionError(f"API request failed: {str(e)}")
    
    def extract(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Extract data from API endpoint.
        
        Args:
            limit: Optional limit on rows to return (applied after fetch)
            
        Returns:
            DataFrame with extracted data
        """
        try:
            response = self._make_request()
            
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                raise ExtractionError("API response is not valid JSON")
            
            self._response_data = response_json
            data = self._extract_data_from_response(response_json)
            
            if not data:
                return pd.DataFrame()
            
            df = pd.DataFrame(data)
            
            if limit and len(df) > limit:
                df = df.head(limit)
            
            self._df = df
            return df
            
        except (ConnectionError, ExtractionError):
            raise
        except Exception as e:
            raise ExtractionError(f"Failed to extract data from API: {str(e)}")
    
    def get_columns(self) -> List[Dict[str, Any]]:
        """Get column information from API response"""
        if self._df is None:
            self.extract(limit=10)
        
        if self._df is None or self._df.empty:
            return []
        
        columns = []
        for col in self._df.columns:
            dtype = str(self._df[col].dtype)
            columns.append({
                "name": col,
                "type": dtype
            })
        return columns
    
    def test_connection(self) -> Dict[str, Any]:
        """Test API endpoint connectivity"""
        try:
            response = self._make_request()
            
            try:
                response_json = response.json()
                data = self._extract_data_from_response(response_json)
                row_count = len(data) if isinstance(data, list) else 1
                
                return {
                    "success": True,
                    "message": f"API accessible. Found {row_count} record(s)",
                    "status_code": response.status_code,
                    "sample_fields": list(data[0].keys()) if data and isinstance(data[0], dict) else []
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "message": "API accessible but response is not JSON",
                    "status_code": response.status_code
                }
                
        except ConnectionError as e:
            return {
                "success": False,
                "message": str(e)
            }
        except ExtractionError as e:
            return {
                "success": False,
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection test failed: {str(e)}"
            }
    
    def preview(self, rows: int = 10) -> Dict[str, Any]:
        """Preview data from API with additional metadata"""
        result = super().preview(rows)
        
        if self._response_data:
            if isinstance(self._response_data, dict):
                result["response_keys"] = list(self._response_data.keys())
        
        return result
