from typing import List, Dict, Optional
from datetime import datetime
from app.core.storage import STORAGE_DIR


def list_uploaded_documents(tenant_id: Optional[str] = None) -> List[Dict]:
    """
    List all uploaded documents from the storage directory.
    
    Args:
        tenant_id: Optional tenant identifier to filter documents. If None, returns all documents.
        
    Returns:
        List of dictionaries containing document information:
        - tenant_id: Tenant identifier
        - filename: Name of the file
        - file_path: Full path to the file
        - file_size: Size of the file in bytes
        - uploaded_at: Timestamp when the file was last modified (upload time)
    """
    uploads_dir = STORAGE_DIR / "raw_uploads"
    documents = []
    
    if not uploads_dir.exists():
        return documents
    
    # If tenant_id is provided, only list documents for that tenant
    if tenant_id:
        tenant_path = uploads_dir / tenant_id
        if tenant_path.exists() and tenant_path.is_dir():
            for file_path in tenant_path.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    documents.append({
                        "tenant_id": tenant_id,
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "file_size": stat.st_size,
                        "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
    else:
        # List all documents from all tenants
        for tenant_dir in uploads_dir.iterdir():
            if tenant_dir.is_dir():
                current_tenant_id = tenant_dir.name
                for file_path in tenant_dir.iterdir():
                    if file_path.is_file():
                        stat = file_path.stat()
                        documents.append({
                            "tenant_id": current_tenant_id,
                            "filename": file_path.name,
                            "file_path": str(file_path),
                            "file_size": stat.st_size,
                            "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
    
    # Sort by uploaded_at (most recent first)
    documents.sort(key=lambda x: x["uploaded_at"], reverse=True)
    
    return documents
