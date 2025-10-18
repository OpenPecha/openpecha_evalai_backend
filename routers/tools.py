from fastapi import APIRouter, HTTPException
import httpx
import os
from typing import Dict, Any, List
from pydantic import BaseModel

router = APIRouter(prefix="/tools", tags=["Tools"])



class ToolsResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    count: int

@router.get("/", response_model=ToolsResponse)
async def get_tools():
    """
    Get the list of available tools from Pecha Studio API.
    Fetches tools from the configured STUDIO_LINK environment variable.
    """
    try:
        # Get studio link from environment variable
        studio_link = os.getenv("STUDIO_LINK")
        tools_url = f"{studio_link}/api/tools"
        
        # Make HTTP request to fetch tools
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(tools_url)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch tools from Pecha Studio API. Status: {response.status_code}"
                )
            
            # Parse and validate the response
            tools_data = response.json()
            
            # Validate the response structure
            if not isinstance(tools_data, dict) or "success" not in tools_data:
                raise HTTPException(
                    status_code=500,
                    detail="Invalid response format from Pecha Studio API"
                )
            
            return ToolsResponse(**tools_data)
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=500,
            detail="Timeout while fetching tools from Pecha Studio API"
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Network error while fetching tools: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error while fetching tools: {str(e)}"
        )
