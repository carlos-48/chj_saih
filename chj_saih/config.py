"""
Configuration module for the CHJ-SAIH client.

This module stores base URLs for the Confederación Hidrográfica del Júcar (CHJ)
Sistema Automático de Información Hidrológica (SAIH) API endpoints.
"""

API_URL = "http://saih.chj.es/chj/saih/stats/datosGrafico"
API_URL = "https://saih.chj.es/admin/variables/valor/"
"""Base URL for fetching sensor statistical data.
This is the base path, specific variable ID and daterange will be appended.
Example: https://saih.chj.es/admin/variables/valor/1775/2024-07-09%2000:00:00/2024-07-10%2006:51:48
"""

# BASE_URL_STATION_LIST is no longer used, station lists are scraped from HTML pages.
BASE_URL_STATION_LIST = None # Explicitly mark as unused or point to main page.
"""DEPRECATED: Base URL for fetching lists of monitoring stations. Now scraped."""
