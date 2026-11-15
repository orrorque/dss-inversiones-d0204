FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit \
    plotly \
    pandas \
    numpy \
    statsmodels \
    yfinance \
    fpdf \
    openpyxl \
    uvicorn

COPY . .

EXPOSE 8502 8501

CMD ["streamlit", "run", "app.py", "--server.port=8502", "--server.headless=true"]
