# Tutorial: Training an EcoTrack Model

**Prerequisites:** [Quickstart Guide](./QUICKSTART.md) completed, Python 3.11+, `ecotrack-ml` package installed, PyTorch 2.1+
**Time:** ~45 minutes
**Difficulty:** Intermediate

---

## Table of Contents

- [1. Overview](#1-overview)
- [2. Understanding the EcoTrackModel Base Class](#2-understanding-the-ecotrackmodel-base-class)
- [3. Preparing Datasets](#3-preparing-datasets)
- [4. Configuring the Trainer](#4-configuring-the-trainer)
- [5. Running Training](#5-running-training)
- [6. Evaluating with ModelEvaluator](#6-evaluating-with-modelevaluator)
- [7. Exporting to ONNX](#7-exporting-to-onnx)
- [8. Registering with ModelRegistry](#8-registering-with-modelregistry)
- [9. Deploying for Inference](#9-deploying-for-inference)
- [10. Next Steps](#10-next-steps)

---

## 1. Overview

EcoTrack's ML engine provides a complete lifecycle for training, evaluating, exporting, and deploying environmental AI models. The engine supports six model architectures across five environmental domains, all unified under a common [`EcoTrackModel`](../../packages/ml/ecotrack_ml/models/base.py:85) base class.

### ML Lifecycle

```
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Dataset  │──▶│  Trainer  │──▶│ Evaluator│──▶│  Export  │──▶│ Registry │
│ prepare  │   │  fit()    │   │ evaluate()│  │  ONNX   │   │ register │
└──────────┘   └───────────┘   └──────────┘   └──────────┘   └──────────┘
                                                                   │
                                                              ┌────▼─────┐
                                                              │ Inference│
                                                              │ Engine   │
                                                              └──────────┘
```

### Available Models

| Model | Module | Task | Domain |
|-------|--------|------|--------|
| Climate TCN | [`climate_forecaster.py`](../../packages/ml/ecotrack_ml/models/climate_forecaster.py) | Forecasting | Climate |
| Land Cover U-Net | [`land_cover.py`](../../packages/ml/ecotrack_ml/models/land_cover.py) | Segmentation | Biodiversity |
| Species Detector | [`species_detector.py`](../../packages/ml/ecotrack_ml/models/species_detector.py) | Classification | Biodiversity |
| Anomaly VAE | [`anomaly_detector.py`](../../packages/ml/ecotrack_ml/models/anomaly_detector.py) | Anomaly Detection | Multi-domain |
| Crop Yield Predictor | [`crop_yield.py`](../../packages/ml/ecotrack_ml/models/crop_yield.py) | Regression | Food Security |

---

## 2. Understanding the EcoTrackModel Base Class

Every EcoTrack model inherits from [`EcoTrackModel`](../../packages/ml/ecotrack_ml/models/base.py:85), which extends `torch.nn.Module` with:

- **Metadata tracking** via [`ModelMetadata`](../../packages/ml/ecotrack_ml/models/base.py:36)
- **Unified prediction** with automatic timing
- **ONNX export** with dynamic batch axes
- **Checkpoint save/load** with metadata preservation

```python
from ecotrack_ml.models.base import EcoTrackModel, ModelMetadata, ModelTask

class MyModel(EcoTrackModel):
    """Custom EcoTrack model."""

    def __init__(self, metadata: ModelMetadata, hidden_dim: int = 128) -> None:
        super().__init__(metadata)
        self.encoder = nn.Linear(metadata.input_shape[0], hidden_dim)
        self.decoder = nn.Linear(hidden_dim, metadata.output_shape[0])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.encoder(x))
        return self.decoder(h)
```

### ModelMetadata

The [`ModelMetadata`](../../packages/ml/ecotrack_ml/models/base.py:36) dataclass tracks model provenance:

```python
metadata = ModelMetadata(
    name="climate_tcn_v2",
    version="0.2.0",
    task=ModelTask.FORECASTING,
    domain="climate",
    description="TCN for 30-day temperature forecasting",
    input_shape=(5, 60),      # (n_variables, window_size)
    output_shape=(30, 5),     # (forecast_horizon, n_variables)
    training_dataset="era5_temperature_2020_2024",
    tags={"region": "global", "resolution": "0.25deg"},
)
```

### ModelTask Enum

The [`ModelTask`](../../packages/ml/ecotrack_ml/models/base.py:19) enum defines supported task types, which determine the evaluation metrics:

| Task | Value | Metrics Used |
|------|-------|-------------|
| `REGRESSION` | `"regression"` | RMSE, MAE, R², MAPE, Bias |
| `CLASSIFICATION` | `"classification"` | Accuracy, Precision, Recall, F1 |
| `SEGMENTATION` | `"segmentation"` | Pixel Accuracy, mIoU, Dice |
| `FORECASTING` | `"forecasting"` | CRPS, Coverage, Sharpness, Skill Score |
| `ANOMALY_DETECTION` | `"anomaly_detection"` | Reconstruction RMSE, MAE, R² |
| `OBJECT_DETECTION` | `"object_detection"` | mAP, IoU |

---

## 3. Preparing Datasets

EcoTrack provides three domain-specific dataset classes in [`ecotrack_ml.training.datasets`](../../packages/ml/ecotrack_ml/training/datasets.py).

### Climate Time Series

[`ClimateTimeSeriesDataset`](../../packages/ml/ecotrack_ml/training/datasets.py:22) creates sliding-window pairs from continuous time-series:

```python
import numpy as np
from ecotrack_ml.training.datasets import ClimateTimeSeriesDataset

# Load your climate data — shape: (time_steps, n_variables)
# Variables: temperature, precipitation, humidity, wind_speed, pressure
data = np.random.randn(3650, 5).astype(np.float32)  # 10 years of daily data

dataset = ClimateTimeSeriesDataset(
    data=data,
    window_size=60,           # 60 days of input
    forecast_horizon=30,      # Predict next 30 days
    transform=None,           # Optional preprocessing
)

print(f"Dataset size: {len(dataset)}")
# Each sample: (input_window, target_window)
x, y = dataset[0]
print(f"Input shape:  {x.shape}")   # (5, 60) — channels-first for TCN
print(f"Target shape: {y.shape}")   # (30, 5)
```

### Satellite Imagery

[`SatelliteImageDataset`](../../packages/ml/ecotrack_ml/training/datasets.py:81) loads GeoTIFF images with lazy LRU caching:

```python
from pathlib import Path
from ecotrack_ml.training.datasets import SatelliteImageDataset

image_paths = sorted(Path("data/sentinel2/images").glob("*.tif"))
label_paths = sorted(Path("data/sentinel2/labels").glob("*.tif"))

dataset = SatelliteImageDataset(
    image_paths=image_paths,
    label_paths=label_paths,
    transform=None,         # Optional augmentation pipeline
    cache_size=128,         # LRU cache for loaded tiles
)

# Each sample: (image, label)
image, label = dataset[0]
print(f"Image shape: {image.shape}")  # (13, 256, 256) — 13 bands
print(f"Label shape: {label.shape}")  # (256, 256) — class IDs
```

### Multi-Modal Crop Data

[`MultiModalCropDataset`](../../packages/ml/ecotrack_ml/training/datasets.py:169) aligns satellite, weather, and soil data:

```python
from ecotrack_ml.training.datasets import MultiModalCropDataset

dataset = MultiModalCropDataset(
    imagery_paths=image_paths,                              # Satellite images
    weather_data=np.random.randn(100, 90, 8),              # (samples, seq_len, features)
    soil_data=np.random.randn(100, 12),                    # (samples, soil_features)
    yields=np.random.uniform(1.0, 6.0, size=100),          # Target yields (t/ha)
    image_transform=None,
)

# Each sample: (input_dict, target)
inputs, target = dataset[0]
print(f"Imagery: {inputs['imagery'].shape}")   # (13, 64, 64)
print(f"Weather: {inputs['weather'].shape}")   # (90, 8)
print(f"Soil:    {inputs['soil'].shape}")      # (12,)
print(f"Yield:   {target.shape}")              # (1,)
```

### Creating DataLoaders

```python
from torch.utils.data import DataLoader, random_split

# Split into train/validation/test
n = len(dataset)
train_size = int(0.7 * n)
val_size = int(0.15 * n)
test_size = n - train_size - val_size

train_set, val_set, test_set = random_split(dataset, [train_size, val_size, test_size])

train_loader = DataLoader(train_set, batch_size=32, shuffle=True, num_workers=4)
val_loader = DataLoader(val_set, batch_size=32, shuffle=False)
test_loader = DataLoader(test_set, batch_size=32, shuffle=False)
```

---

## 4. Configuring the Trainer

The [`EcoTrackTrainer`](../../packages/ml/ecotrack_ml/training/trainer.py:87) is configured through [`TrainerConfig`](../../packages/ml/ecotrack_ml/training/trainer.py:36):

```python
from pathlib import Path
from ecotrack_ml.training.trainer import TrainerConfig

config = TrainerConfig(
    max_epochs=100,                    # Maximum training epochs
    batch_size=32,                     # Informational (actual batch from DataLoader)
    learning_rate=1e-3,                # Base learning rate
    weight_decay=1e-4,                 # L2 regularisation
    early_stopping_patience=10,        # Stop after 10 epochs without improvement
    gradient_clip_norm=1.0,            # Max gradient norm (0 = disabled)
    log_interval=50,                   # Log every N batches
    checkpoint_dir=Path("checkpoints"),# Checkpoint directory
    experiment_name="climate_tcn_v2",  # Experiment identifier
)
```

### Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_epochs` | `int` | `100` | Upper limit on training epochs |
| `batch_size` | `int` | `32` | Informational batch size |
| `learning_rate` | `float` | `1e-3` | Base learning rate for the optimiser |
| `weight_decay` | `float` | `1e-4` | L2 weight decay coefficient |
| `early_stopping_patience` | `int` | `10` | Epochs to wait before early stopping |
| `gradient_clip_norm` | `float` | `1.0` | Maximum gradient norm for clipping |
| `log_interval` | `int` | `50` | Training log frequency (batches) |
| `checkpoint_dir` | `Path` | `checkpoints/` | Directory for saving checkpoints |
| `experiment_name` | `str` | `ecotrack_experiment` | Human-readable experiment name |

---

## 5. Running Training

### Complete Training Example

```python
import torch
import torch.nn as nn
import numpy as np
from ecotrack_ml.models.base import ModelMetadata, ModelTask
from ecotrack_ml.training.trainer import EcoTrackTrainer, TrainerConfig
from ecotrack_ml.training.datasets import ClimateTimeSeriesDataset
from torch.utils.data import DataLoader, random_split

# 1. Prepare data
data = np.load("data/climate/era5_temperature.npy")  # (time_steps, n_vars)
dataset = ClimateTimeSeriesDataset(data, window_size=60, forecast_horizon=30)

train_size = int(0.8 * len(dataset))
val_size = len(dataset) - train_size
train_set, val_set = random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
val_loader = DataLoader(val_set, batch_size=32)

# 2. Create model
metadata = ModelMetadata(
    name="climate_tcn_v2",
    version="0.2.0",
    task=ModelTask.FORECASTING,
    domain="climate",
    description="TCN for temperature forecasting",
    input_shape=(5, 60),
    output_shape=(30, 5),
)

# Import your model class (e.g., ClimateTCN from ecotrack_ml.models)
from ecotrack_ml.models.climate_forecaster import ClimateTCN
model = ClimateTCN(metadata=metadata)
print(f"Parameters: {model.count_parameters():,}")

# 3. Configure training
config = TrainerConfig(
    max_epochs=100,
    learning_rate=1e-3,
    early_stopping_patience=10,
    experiment_name="climate_tcn_v2",
)

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=config.learning_rate,
    weight_decay=config.weight_decay,
)

criterion = nn.MSELoss()

# 4. Train
trainer = EcoTrackTrainer(
    model=model,
    optimizer=optimizer,
    criterion=criterion,
    config=config,
)

result = trainer.fit(train_loader, val_loader)

# 5. Inspect results
print(f"Best epoch: {result.best_epoch}")
print(f"Best val loss: {result.best_metrics.get('val_loss', 'N/A'):.6f}")
print(f"Training time: {result.training_time_s:.1f}s")
print(f"Final train losses: {result.train_losses[-3:]}")
```

### Understanding the Training Loop

The [`EcoTrackTrainer.fit()`](../../packages/ml/ecotrack_ml/training/trainer.py:123) method executes:

1. **Per-epoch training** — Forward pass → loss → backward pass → gradient clipping → optimiser step
2. **Validation** — Loss computation on the validation set (no gradients)
3. **Early stopping** — Tracks best validation loss; stops after `patience` epochs without improvement
4. **LR scheduling** — Cosine annealing from `learning_rate` to near-zero over `max_epochs`
5. **Checkpointing** — Saves model weights, optimiser state, and validation loss at each improvement
6. **Best model restore** — Loads best weights after training completes

### TrainingResult

The returned [`TrainingResult`](../../packages/ml/ecotrack_ml/training/trainer.py:63) contains:

```python
@dataclass
class TrainingResult:
    train_losses: list[float]     # Per-epoch average training loss
    val_losses: list[float]       # Per-epoch average validation loss
    best_epoch: int               # Epoch with best validation loss
    best_metrics: dict[str, float]# Metrics at best epoch
    training_time_s: float        # Total wall-clock time
```

---

## 6. Evaluating with ModelEvaluator

The [`ModelEvaluator`](../../packages/ml/ecotrack_ml/evaluation/evaluator.py:54) provides comprehensive evaluation with task-appropriate metrics:

```python
from ecotrack_ml.evaluation.evaluator import ModelEvaluator

evaluator = ModelEvaluator(device=torch.device("cuda"))

# Standard evaluation
report = evaluator.evaluate(
    model=model,
    dataloader=test_loader,
    task_type=ModelTask.FORECASTING,
)

print("Metrics:")
for key, value in report.metrics.items():
    if isinstance(value, float):
        print(f"  {key}: {value:.4f}")
```

### Evaluation with Uncertainty

Enable MC Dropout for uncertainty estimation:

```python
report = evaluator.evaluate(
    model=model,
    dataloader=test_loader,
    task_type=ModelTask.FORECASTING,
    mc_dropout_samples=10,  # 10 stochastic forward passes
)

print(f"Mean uncertainty: {report.uncertainty_estimates.mean():.4f}")
```

### EvaluationReport Contents

The returned [`EvaluationReport`](../../packages/ml/ecotrack_ml/evaluation/evaluator.py:36) contains:

| Field | Type | Description |
|-------|------|-------------|
| `metrics` | `dict[str, Any]` | Task-specific metric values |
| `predictions` | `np.ndarray` | All model predictions |
| `ground_truth` | `np.ndarray` | All ground truth values |
| `uncertainty_estimates` | `np.ndarray \| None` | Per-sample uncertainty (MC Dropout) |
| `calibration_data` | `dict \| None` | Reliability diagram data |

### Manual Metric Computation

You can also use the metric classes directly:

```python
from ecotrack_ml.evaluation.metrics import (
    RegressionMetrics,
    ForecastMetrics,
    SegmentationMetrics,
)

# Regression metrics
reg = RegressionMetrics(y_true=ground_truth, y_pred=predictions)
print(reg.compute_all())
# {'rmse': 0.42, 'mae': 0.31, 'r_squared': 0.89, 'mape': 4.2, 'bias': -0.02}

# Forecast metrics (with uncertainty)
forecast = ForecastMetrics(
    y_true=ground_truth,
    y_pred_mean=predictions,
    y_pred_std=uncertainty,
    reference_mse=1.5,  # Climatological baseline MSE
)
print(forecast.compute_all())
# {'crps': 0.28, 'coverage_95': 0.93, 'sharpness': 1.8, 'skill_score': 0.72}
```

---

## 7. Exporting to ONNX

Export trained models for production deployment:

```python
from pathlib import Path

# Create a dummy input matching your model's expected shape
dummy_input = torch.randn(1, 5, 60)  # (batch, n_vars, window_size)

# Export to ONNX
onnx_path = model.export_onnx(
    path=Path("models/climate_tcn_v2.onnx"),
    dummy_input=dummy_input,
)
print(f"Exported to: {onnx_path}")
```

The export uses:
- **Opset version 17** for broad compatibility
- **Dynamic batch axis** so the model accepts any batch size
- Named inputs (`"input"`) and outputs (`"output"`)

### Verifying the ONNX Model

```python
import onnxruntime as ort

session = ort.InferenceSession(str(onnx_path))
input_name = session.get_inputs()[0].name

# Run inference
test_input = np.random.randn(4, 5, 60).astype(np.float32)
result = session.run(None, {input_name: test_input})
print(f"Output shape: {result[0].shape}")  # (4, 30, 5)
```

---

## 8. Registering with ModelRegistry

The [`ModelRegistry`](../../packages/ml/ecotrack_ml/registry/registry.py:36) provides versioned model management:

```python
from ecotrack_ml.registry.registry import ModelRegistry

# Initialize registry (local fallback when MLflow unavailable)
registry = ModelRegistry(
    tracking_uri=None,              # Set to MLflow URI if available
    local_root="model_registry",    # Local storage directory
)

# Register the trained model
version = registry.register_model(
    model=model,
    metadata=model.metadata,
    metrics=report.metrics,
    artifacts=[onnx_path],          # Attach ONNX file as artifact
)
print(f"Registered version: {version}")
```

### Promoting Model Stages

```python
# Promote to staging for integration testing
registry.promote_model("climate_tcn_v2", version, stage="staging")

# After validation, promote to production
registry.promote_model("climate_tcn_v2", version, stage="production")
```

### Listing and Comparing Models

```python
# List all models in the climate domain
models = registry.list_models(domain="climate")
for m in models:
    print(f"  {m['name']} v{m['version']} — {m.get('stage', 'none')}")

# Compare metrics across versions
comparison = registry.compare_models(
    name="climate_tcn_v2",
    versions=["0.1.0", "0.2.0"],
)
for version, metrics in comparison.items():
    print(f"  v{version}: RMSE={metrics.get('rmse', 'N/A')}")
```

### Loading a Registered Model

```python
from ecotrack_ml.models.climate_forecaster import ClimateTCN

loaded_model = registry.load_model(
    name="climate_tcn_v2",
    version="0.2.0",
    model_class=ClimateTCN,
)
```

---

## 9. Deploying for Inference

The [`InferenceEngine`](../../packages/ml/ecotrack_ml/inference/engine.py:28) provides production-ready inference:

### PyTorch Backend

```python
from ecotrack_ml.inference.engine import InferenceEngine
from ecotrack_ml.models.climate_forecaster import ClimateTCN

engine = InferenceEngine(device=torch.device("cuda"))

# Load from checkpoint
engine.load_model(
    path="model_registry/climate_tcn_v2/0.2.0/model.pt",
    backend="pytorch",
    model_class=ClimateTCN,
)

# Run inference
inputs = np.random.randn(16, 5, 60).astype(np.float32)
result = engine.predict(inputs, batch_size=8)
print(f"Predictions: {result.predictions.shape}")
print(f"Inference time: {result.inference_time_ms:.1f}ms")
```

### ONNX Backend (Recommended for Production)

```python
engine = InferenceEngine()

engine.load_model(
    path="models/climate_tcn_v2.onnx",
    backend="onnx",
)

result = engine.predict(inputs, batch_size=64)
print(f"ONNX inference time: {result.inference_time_ms:.1f}ms")
```

### Inference with Uncertainty

```python
result = engine.predict_with_uncertainty(
    inputs=inputs,
    n_samples=10,       # MC Dropout forward passes
    batch_size=8,
)
print(f"Mean predictions: {result.predictions.shape}")
print(f"Uncertainty (std): {result.uncertainty.shape}")
print(f"MC samples used: {result.metadata['n_mc_samples']}")
```

### Serving via the ML API

The trained model can be served through the FastAPI ML API:

```python
# In apps/ml-api/main.py, models are loaded at startup
# and exposed via REST endpoints:

# POST /predict
# {
#   "model_name": "climate_tcn_v2",
#   "version": "0.2.0",
#   "inputs": [[...]]
# }
```

---

## 10. Next Steps

- **Experiment with augmentations** — See [`ecotrack_ml.training.augmentations`](../../packages/ml/ecotrack_ml/training/augmentations.py) for satellite imagery transforms
- **Build an ensemble** — Use [`ecotrack_ml.inference.ensemble`](../../packages/ml/ecotrack_ml/inference/ensemble.py) for multi-model uncertainty
- **Connect to the agent system** — Follow the [Agent Development Tutorial](./AGENT_DEVELOPMENT.md) to make your model accessible to agents
- **Set up scheduled training** — Use the worker tasks in [`ecotrack_worker/tasks/model_training.py`](../../apps/worker/ecotrack_worker/tasks/model_training.py)
- **Read the whitepaper** — See the [Research Whitepaper](../whitepaper/WHITEPAPER.md) for architectural rationale

---

*See also: [Data Ingestion Tutorial](./DATA_INGESTION.md) · [Agent Development Tutorial](./AGENT_DEVELOPMENT.md) · [API Documentation](../../API.md)*
