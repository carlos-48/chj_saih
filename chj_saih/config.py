"""
Configuration module for the CHJ-SAIH client.

This module stores base URLs for the Confederación Hidrográfica del Júcar (CHJ)
Sistema Automático de Información Hidrológica (SAIH) API endpoints.
"""

API_URL = "https://saih.chj.es/api/v1/datos/grafica"
"""Base URL for fetching sensor statistical data."""

BASE_URL_STATION_LIST = "https://saih.chj.es/api/v1/geoserver/{sensor_type}/ows?service=WFS&request=GetFeature&typeName={sensor_type}&outputFormat=application/json"
"""Base URL for fetching lists of monitoring stations."""
