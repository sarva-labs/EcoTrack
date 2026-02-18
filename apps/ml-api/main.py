import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="EcoTrack ML API",
    description="Machine Learning API for tree detection and species classification",
    version="1.0.0",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DetectionResult(BaseModel):
    """Model for tree detection results"""
    species: str
    confidence: float
    bounding_box: List[float]
    estimated_age: Optional[int] = None
    root_spread: Optional[float] = None


class ClassificationResult(BaseModel):
    """Model for species classification results"""
    species: str
    confidence: float
    alternative_species: List[dict]


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "EcoTrack ML API is running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "models": {
            "tree_detection": "loaded",
            "species_classification": "loaded",
            "soil_classification": "loaded",
        },
    }


@app.post("/detect/trees", response_model=List[DetectionResult])
async def detect_trees(file: UploadFile = File(...)):
    """
    Detect trees in an image using YOLOv8
    
    Args:
        file: Image file for tree detection
        
    Returns:
        List of detected trees with bounding boxes and confidence scores
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Placeholder implementation
    # TODO: Implement actual YOLOv8 detection
    return [
        DetectionResult(
            species="Unknown",
            confidence=0.85,
            bounding_box=[100, 100, 200, 300],
            estimated_age=None,
            root_spread=None,
        )
    ]


@app.post("/classify/species", response_model=ClassificationResult)
async def classify_species(file: UploadFile = File(...)):
    """
    Classify tree species from an image
    
    Args:
        file: Image file containing a tree
        
    Returns:
        Classification result with species and confidence
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Placeholder implementation
    # TODO: Implement actual species classification
    return ClassificationResult(
        species="Oak Tree",
        confidence=0.92,
        alternative_species=[
            {"species": "Maple", "confidence": 0.05},
            {"species": "Birch", "confidence": 0.03},
        ],
    )


@app.post("/classify/soil")
async def classify_soil(file: UploadFile = File(...)):
    """
    Classify soil type from an image
    
    Args:
        file: Image file of soil
        
    Returns:
        Soil classification result
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Placeholder implementation
    # TODO: Implement actual soil classification
    return {
        "soil_type": "Loamy",
        "confidence": 0.87,
        "properties": {
            "moisture": "medium",
            "fertility": "high",
        },
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
