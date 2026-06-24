#!/usr/bin/env python3
"""
generar_dashboard_momentum.py
Redirecciona al generador unificado en generar_dashboard_comparativo.py
para evitar duplicación de código y mantener compatibilidad con GHA.
"""
from generar_dashboard_comparativo import generar_dashboard

if __name__ == "__main__":
    generar_dashboard()
