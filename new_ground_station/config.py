#NOT USED YET
# """Configuration management for telemetry display."""
# import json
# from pathlib import Path
# from typing import Dict, List, Any, Optional
# from pydantic import BaseModel, Field


# class FieldMetadata(BaseModel):
#     """Metadata for a single telemetry field."""
#     name: str
#     unit: str
#     precision: int
#     description: Optional[str] = None


# class PanelConfig(BaseModel):
#     """Configuration for a dashboard panel."""
#     id: str
#     type: str  # indicator, float, chart, multi_chart, grouped, boolean_grid, mission_timer
#     title: str
#     order: int
#     fields: Optional[List[str]] = None
#     unit: Optional[str] = None
#     precision: Optional[int] = None
#     mapping: Optional[List[str]] = None  # For indicator type
#     items: Optional[List[Dict[str, Any]]] = None  # For grouped/boolean_grid types
#     labels: Optional[List[str]] = None  # For multi_chart type
#     colors: Optional[List[str]] = None  # For multi_chart type
#     chart_color: Optional[str] = None  # For single chart type


# class TelemetryConfig(BaseModel):
#     """Complete telemetry configuration."""
#     panels: List[PanelConfig]
#     field_metadata: Dict[str, FieldMetadata]

#     def get_all_fields(self) -> List[str]:
#         """Get list of all unique telemetry fields used in panels."""
#         fields = set()

#         for panel in self.panels:
#             if panel.fields:
#                 fields.update(panel.fields)
#             if panel.items:
#                 for item in panel.items:
#                     if 'field' in item:
#                         fields.add(item['field'])

#         return sorted(list(fields))

#     def get_panel_by_id(self, panel_id: str) -> Optional[PanelConfig]:
#         """Get panel configuration by ID."""
#         for panel in self.panels:
#             if panel.id == panel_id:
#                 return panel
#         return None

#     def get_field_metadata(self, field: str) -> Optional[FieldMetadata]:
#         """Get metadata for a specific field."""
#         return self.field_metadata.get(field)


# def load_config(config_path: str = "public/config.json") -> TelemetryConfig:
#     """
#     Load telemetry configuration from JSON file.

#     Args:
#         config_path: Path to configuration file

#     Returns:
#         TelemetryConfig instance

#     Raises:
#         FileNotFoundError: If config file doesn't exist
#         ValueError: If config is invalid
#     """
#     path = Path(config_path)

#     if not path.exists():
#         raise FileNotFoundError(f"Configuration file not found: {config_path}")

#     with open(path, 'r') as f:
#         data = json.load(f)

#     try:
#         return TelemetryConfig(**data)
#     except Exception as e:
#         raise ValueError(f"Invalid configuration: {e}") from e


# def get_default_config() -> TelemetryConfig:
#     """Get default configuration (loads from public/config.json)."""
#     return load_config()
