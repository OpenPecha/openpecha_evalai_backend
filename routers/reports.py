from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from datetime import datetime
from database import get_db
from auth import get_current_active_user
from models.user import User
import csv
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["Reports"])

db_dependency = Depends(get_db)

@router.get("/download-votes-report")
async def download_votes_report(
    db: Session = db_dependency
):
    """
    Download a CSV report of all voting data with translation details.
    Returns a CSV file with filename format: {date}_report.csv
    """
    try:
        # SQL query to get comprehensive voting data
        query = text("""
            SELECT
              tj.id AS translation_job_id,
              tj.source_text AS original_text,
              tj.target_language,
              tj."template",
              v.id AS vote_id,
              v.created_at AS vote_created_at,
              u.username AS voter_username,
              v."comment" AS vote_comment,
              v.response_time_ms,
              v.is_tie,
              a.id AS output_a_id,
              a.streamed_text AS output_a_text,
              mv_a.version AS model_a_version,
              mv_a.provider AS model_a_provider,
              b.id AS output_b_id,
              b.streamed_text AS output_b_text,
              mv_b.version AS model_b_version,
              mv_b.provider AS model_b_provider,
              v.winner_id,
              CASE
                WHEN v.is_tie = 1 THEN 'tie'
                WHEN v.is_tie = 2 THEN 'none'
                WHEN v.winner_id = a.id THEN 'A'
                WHEN v.winner_id = b.id THEN 'B'
                ELSE NULL
              END AS winner_choice
            FROM public.vote v
            JOIN public.translation_job tj
              ON tj.id = v.translation_job_id
            LEFT JOIN public.translation_output a
              ON a.id = v.translation_output_a_id
            LEFT JOIN public.translation_output b
              ON b.id = v.translation_output_b_id
            LEFT JOIN public.model_version mv_a
              ON mv_a.id = a.model_version_id
            LEFT JOIN public.model_version mv_b
              ON mv_b.id = b.model_version_id
            LEFT JOIN public."user" u
              ON u.id = v.user_id
            ORDER BY v.created_at DESC, tj.id;
        """)
        
        # Execute the query
        result = db.execute(query)
        rows = result.fetchall()
        
        # Get column names from the result
        columns = result.keys()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(columns)
        
        # Write data rows
        for row in rows:
            # Convert row to list and handle None values
            row_data = []
            for value in row:
                if value is None:
                    row_data.append('')
                elif isinstance(value, datetime):
                    row_data.append(value.isoformat())
                else:
                    row_data.append(str(value))
            writer.writerow(row_data)
        
        # Get the CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Create filename with current date
        current_date = datetime.now().strftime("%Y%m%d")
        filename = f"{current_date}_report.csv"
        
        # Return the CSV as a streaming response
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error generating CSV report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )
