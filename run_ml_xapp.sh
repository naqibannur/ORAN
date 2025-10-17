#!/bin/bash

# Script to run ML-enhanced xApps

echo "O-RAN SC RIC - ML-Enhanced xApps"
echo "================================="

if [ $# -eq 0 ]; then
    echo "Usage: ./run_ml_xapp.sh <xapp_name> [options]"
    echo ""
    echo "Available ML xApps:"
    echo "  ml_resource_optimizer    - Predictive resource allocation optimizer"
    echo "  anomaly_detector         - Network performance anomaly detector"
    echo "  qos_traffic_steerer      - QoS-aware traffic steering controller"
    echo ""
    echo "Example:"
    echo "  ./run_ml_xapp.sh ml_resource_optimizer --metrics=DRB.UEThpDl,DRB.UEThpUl"
    exit 1
fi

XAPP_NAME=$1
shift

case $XAPP_NAME in
    "ml_resource_optimizer")
        echo "Running ML Resource Optimizer xApp..."
        docker compose exec python_xapp_runner ./ml_resource_optimizer.py "$@"
        ;;
    "anomaly_detector")
        echo "Running Anomaly Detector xApp..."
        docker compose exec python_xapp_runner ./anomaly_detector.py "$@"
        ;;
    "qos_traffic_steerer")
        echo "Running QoS Traffic Steerer xApp..."
        docker compose exec python_xapp_runner ./qos_traffic_steerer.py "$@"
        ;;
    *)
        echo "Unknown xApp: $XAPP_NAME"
        echo "Available ML xApps: ml_resource_optimizer, anomaly_detector, qos_traffic_steerer"
        exit 1
        ;;
esac