#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "🚀 Iniciando Sistema DSS · Inversiones D-02-04..."
./dss_env/bin/streamlit run app.py --server.port 8502
