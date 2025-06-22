ARG AIRFLOW_VERSION=3.0.2
FROM apache/airflow:${AIRFLOW_VERSION}

# Switch back to airflow user
USER airflow

# Copy peakflow module
COPY --chown=airflow:root ./application/peakflow /opt/peakflow

# Install peakflow requirements first
RUN pip install --no-cache-dir -r /opt/peakflow/requirements.txt

# Install peakflow module in editable mode
RUN pip install --no-cache-dir -e /opt/peakflow

# Ensure Apache Airflow is properly installed
RUN pip install apache-airflow==${AIRFLOW_VERSION}


# Set PYTHONPATH to include peakflow
ENV PYTHONPATH="/opt/peakflow"

# Set working directory
WORKDIR /opt/airflow
