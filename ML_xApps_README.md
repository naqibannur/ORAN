# ML-Enhanced xApps for O-RAN SC RIC

This document provides detailed information about the machine learning enhanced xApps created for the O-RAN Software Community (SC) Near-Real-time RIC platform. These xApps leverage ML techniques to optimize 5G network performance through intelligent resource allocation, anomaly detection, and traffic steering.

## Table of Contents

1. [Overview](#overview)
2. [ML xApps Description](#ml-xapps-description)
   - [ML Resource Optimizer](#ml-resource-optimizer)
   - [Anomaly Detector](#anomaly-detector)
   - [QoS Traffic Steerer](#qos-traffic-steerer)
3. [Technical Implementation](#technical-implementation)
4. [Prerequisites](#prerequisites)
5. [Deployment Instructions](#deployment-instructions)
6. [Running the ML xApps](#running-the-ml-xapps)
7. [Configuration Options](#configuration-options)
8. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
9. [Performance Considerations](#performance-considerations)
10. [ML Model Training](#ml-model-training)
    - [Training Data Requirements](#training-data-requirements)
    - [Data Collection Process](#data-collection-process)
    - [Training Procedures](#training-procedures)
    - [Model Evaluation](#model-evaluation)
11. [Extending the ML xApps](#extending-the-ml-xapps)

## Overview

The ML-enhanced xApps extend the capabilities of the standard O-RAN SC RIC platform by incorporating machine learning algorithms to make intelligent decisions about network resource allocation, anomaly detection, and traffic management. These xApps collect performance metrics from the RAN via E2SM-KPM interfaces and send control commands via E2SM-RC interfaces.

## ML xApps Description

### ML Resource Optimizer

The ML Resource Optimizer xApp uses machine learning to predict optimal resource allocation for User Equipment (UE) based on historical traffic patterns and current network conditions.

**Key Features:**
- Collects historical metrics for each UE
- Trains Random Forest models to predict optimal PRB (Physical Resource Block) settings
- Dynamically adjusts resource allocation based on predicted needs
- Continuously improves predictions as more data is collected

**How It Works:**
1. Subscribes to KPM metrics from gNBs
2. Maintains historical data for each UE
3. Extracts features from current and historical metrics
4. Uses trained ML models to predict optimal PRB settings
5. Sends control commands to adjust PRB quotas

### Anomaly Detector

The Anomaly Detector xApp uses statistical methods to detect anomalous network behavior and trigger appropriate corrective actions.

**Key Features:**
- Maintains historical metrics for statistical analysis
- Uses Z-score based anomaly detection
- Implements cooldown periods to avoid excessive alerts
- Can trigger corrective actions based on anomaly type

**How It Works:**
1. Collects KPM metrics from the network
2. Maintains statistical profiles for each metric
3. Calculates Z-scores to identify anomalies
4. Implements cooldown mechanisms to prevent alert flooding
5. Logs anomalies and can trigger corrective actions

### QoS Traffic Steerer

The QoS Traffic Steerer xApp classifies traffic types based on QoS requirements and steers traffic to appropriate cells to maintain service quality.

**Key Features:**
- Classifies traffic into different types (voice, video, gaming, etc.)
- Monitors QoS violations for each traffic type
- Evaluates cell load conditions
- Recommends traffic steering to maintain QoS requirements

**How It Works:**
1. Analyzes throughput patterns to classify traffic types
2. Monitors QoS metrics against defined profiles
3. Evaluates cell load conditions
4. Recommends steering actions for QoS violations

## Technical Implementation

### Architecture

The ML xApps follow the standard xApp architecture:

```
[xApp] ↔ [xApp Framework] ↔ [RMR] ↔ [RIC Platform] ↔ [E2 Agent/gNB]
```

### Dependencies

The ML xApps require the following Python libraries:
- numpy
- scipy
- scikit-learn
- joblib

These dependencies have been added to the Dockerfile for the python_xapp_runner container.

### Data Flow

1. **Subscription Phase:**
   - xApp subscribes to KPM metrics using E2SM-KPM
   - Subscription requests are sent to Subscription Manager via REST API
   - RIC entities acknowledge subscriptions

2. **Data Collection Phase:**
   - gNBs send RIC Indication messages with KPM metrics
   - Messages are routed via RMR to the xApp
   - xApp processes and stores metrics

3. **Analysis Phase:**
   - ML algorithms process collected data
   - Decisions are made based on analysis results

4. **Action Phase:**
   - Control commands are sent via E2SM-RC
   - RIC entities execute control actions

## Prerequisites

Before deploying the ML xApps, ensure you have:

1. **Hardware Requirements:**
   - Modern CPU with at least 4 cores
   - 8GB RAM minimum (16GB recommended)
   - 20GB free disk space
   - Network interface capable of handling RIC traffic

2. **Software Requirements:**
   - Docker Engine 20.10 or higher
   - Docker Compose 1.29 or higher
   - Git
   - Python 3.8 (for local development)

3. **Network Requirements:**
   - Access to O-RAN SC RIC Docker images
   - Proper network connectivity between RIC components
   - SCTP support for E2 interface

## Deployment Instructions

### Step 1: Clone the Repository

```bash
git clone https://github.com/srsran/oran-sc-ric.git
cd oran-sc-ric
```

### Step 2: Build the Docker Images

The Docker images need to be built with the updated dependencies:

```bash
docker compose build
```

This will build all required containers including the python_xapp_runner with ML dependencies.

### Step 3: Start the RIC Platform

Start the RIC platform in detached mode:

```bash
docker compose up -d
```

Wait for all services to initialize (this may take a few minutes for the first run).

### Step 4: Verify RIC Services

Check that all RIC services are running:

```bash
docker compose ps
```

You should see all services in the "running" state.

### Step 5: Connect 5G RAN (Optional for Real Deployment)

To connect a real 5G RAN:

1. Configure your gNB with E2 agent to connect to the RIC IP
2. Ensure SCTP connectivity on port 36421
3. Start your gNB and verify connection to RIC

For testing purposes, you can use the srsRAN setup described in the main README.

## Running the ML xApps

### Running ML Resource Optimizer

```bash
docker compose exec python_xapp_runner ./ml_resource_optimizer.py --metrics=DRB.UEThpDl,DRB.UEThpUl
```

### Running Anomaly Detector

```bash
docker compose exec python_xapp_runner ./anomaly_detector.py --metrics=DRB.UEThpDl,DRB.UEThpUl,RRC.ConnEstabSucc
```

### Running QoS Traffic Steerer

```bash
docker compose exec python_xapp_runner ./qos_traffic_steerer.py --metrics=DRB.UEThpDl,DRB.UEThpUl
```

### Using the Helper Script

You can also use the provided helper script:

```bash
# Make the script executable
chmod +x run_ml_xapp.sh

# Run the xApps using the script
./run_ml_xapp.sh ml_resource_optimizer --metrics=DRB.UEThpDl,DRB.UEThpUl
./run_ml_xapp.sh anomaly_detector --metrics=DRB.UEThpDl,DRB.UEThpUl,RRC.ConnEstabSucc
./run_ml_xapp.sh qos_traffic_steerer --metrics=DRB.UEThpDl,DRB.UEThpUl
```

## Configuration Options

All ML xApps support the following command-line arguments:

### Common Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--http_server_port` | 8090-8097 | HTTP server listen port |
| `--rmr_port` | 4560-4567 | RMR port |
| `--e2_node_id` | gnbd_001_001_00019b_0 | E2 Node ID |
| `--ran_func_id` | 2 | RAN function ID |
| `--kpm_report_style` | 4 | KPM Report Style ID |
| `--ue_ids` | 0 | Comma-separated UE IDs |
| `--metrics` | Varies | Comma-separated metrics |

### ML Resource Optimizer Specific Options

| Argument | Default | Description |
|----------|---------|-------------|
| (Uses common arguments) | | |

### Anomaly Detector Specific Options

| Argument | Default | Description |
|----------|---------|-------------|
| (Uses common arguments) | | |

### QoS Traffic Steerer Specific Options

| Argument | Default | Description |
|----------|---------|-------------|
| (Uses common arguments) | | |

## Monitoring and Troubleshooting

### Monitoring xApp Output

To monitor the output of running xApps:

```bash
docker compose logs python_xapp_runner
```

### Stopping xApps

To stop a running xApp, use Ctrl+C in the terminal where it's running, or:

```bash
docker compose exec python_xapp_runner pkill -f <xapp_filename>
```

### Common Issues

1. **xApp fails to start:**
   - Check that all RIC services are running
   - Verify E2 node ID is correct
   - Ensure metrics names are valid

2. **No metrics received:**
   - Check RIC-E2 connection
   - Verify gNB is sending metrics
   - Confirm subscription was successful

3. **ML models not training:**
   - Ensure sufficient data is being collected
   - Check that training data is being stored

## Performance Considerations

### Resource Usage

The ML xApps have the following resource requirements:

- **CPU:** 1-2 cores per xApp
- **Memory:** 512MB-1GB per xApp
- **Disk:** Minimal (logs and model storage)

### Scaling Considerations

For production deployments:

1. **Multiple xApps:** Each xApp can run in its own container
2. **Load Balancing:** Distribute xApps across multiple hosts
3. **Model Persistence:** Store trained models for faster startup

### Latency Requirements

- **Data Collection:** 1-5 second intervals
- **Model Inference:** <100ms
- **Control Actions:** <1 second

## ML Model Training

### Training Data Requirements

Each ML xApp requires specific types of data for effective training:

#### ML Resource Optimizer
- **Input Features:**
  - Current DL throughput per UE
  - Current UL throughput per UE
  - Historical average DL throughput (10-sample window)
  - Historical average UL throughput (10-sample window)
  - Throughput trend (difference between recent and older samples)
  - History length (number of collected samples)
  
- **Target Variables:**
  - Optimal PRB setting (classification: high=100 or low=10)
  - Handover necessity (binary: 0=No, 1=Yes)

#### Anomaly Detector
- **Input Data:**
  - Time-series metrics for each UE and cell
  - Statistical profiles (mean, standard deviation)
  - Historical metric values for Z-score calculation

#### QoS Traffic Steerer
- **Input Features:**
  - DL throughput patterns
  - UL throughput patterns
  - Throughput variance
  - Connection success rates
  - Cell load indicators

- **Target Variables:**
  - Traffic type classification (voice, video, gaming, web, file_transfer)
  - QoS violation occurrence (binary: 0=No, 1=Yes)
  - Steering necessity (binary: 0=No, 1=Yes)

### Data Collection Process

The ML xApps automatically collect training data during operation:

1. **Automatic Data Collection:**
   - Metrics are collected at regular intervals (configurable)
   - Historical data is maintained in sliding windows
   - Feature extraction happens in real-time

2. **Data Storage:**
   - Data is stored in memory buffers (not persisted to disk)
   - Buffers have configurable maximum lengths
   - Old data is automatically removed to manage memory

3. **Feature Engineering:**
   - Statistical features (mean, variance, trends)
   - Temporal features (time-based patterns)
   - Domain-specific features (network KPIs)

### Training Procedures

#### ML Resource Optimizer Training
The ML Resource Optimizer uses online learning with the following process:

1. **Data Accumulation:**
   - Collects features and outcomes for 20+ samples
   - Stores training data in memory buffers
   - Maintains separate datasets for PRB prediction and handover prediction

2. **Model Training:**
   - Trains Random Forest models when sufficient data is available
   - Uses StandardScaler for feature normalization
   - Retrains models periodically as new data arrives

3. **Training Triggers:**
   - Initial training after 20 samples
   - Retraining every 50 new samples
   - Manual retraining capability

#### Anomaly Detector Training
The Anomaly Detector uses statistical methods that don't require explicit training:

1. **Statistical Profile Building:**
   - Builds mean and standard deviation profiles for each metric
   - Updates profiles incrementally as new data arrives
   - Maintains sufficient history for reliable statistics (30+ samples)

2. **Anomaly Detection:**
   - Calculates Z-scores in real-time
   - Uses configurable thresholds (default: 3.0 standard deviations)
   - Implements cooldown mechanisms to prevent alert flooding

#### QoS Traffic Steerer Training
The QoS Traffic Steerer uses rule-based classification that adapts over time:

1. **Traffic Classification:**
   - Uses throughput patterns to classify traffic types
   - Maintains history for more accurate classification
   - Updates classifications as new data arrives

2. **QoS Monitoring:**
   - Compares actual metrics against QoS profiles
   - Counts violations to trigger steering decisions
   - Adjusts thresholds based on network conditions

### Model Evaluation

#### Performance Metrics

1. **ML Resource Optimizer:**
   - PRB Prediction Accuracy: Percentage of correct PRB setting predictions
   - Handover Prediction Accuracy: Percentage of correct handover decisions
   - Resource Efficiency: Comparison of predicted vs actual resource usage

2. **Anomaly Detector:**
   - Detection Rate: Percentage of actual anomalies correctly identified
   - False Positive Rate: Percentage of normal behavior flagged as anomalous
   - Response Time: Time from anomaly occurrence to detection

3. **QoS Traffic Steerer:**
   - Classification Accuracy: Percentage of correctly classified traffic types
   - QoS Compliance: Percentage of time QoS requirements are met
   - Steering Effectiveness: Improvement in QoS metrics after steering

#### Evaluation Methods

1. **Online Evaluation:**
   - Continuous monitoring of prediction accuracy
   - Real-time performance metrics calculation
   - Automatic model retraining when performance degrades

2. **Offline Evaluation:**
   - Historical data analysis for detailed performance assessment
   - Cross-validation for model robustness testing
   - A/B testing for comparing different model versions

#### Model Persistence

Currently, models are not persisted between xApp restarts. For production deployments, consider:

1. **Model Checkpointing:**
   - Periodic saving of trained models to disk
   - Loading models at startup for faster initialization
   - Version control for model updates

2. **Transfer Learning:**
   - Using pre-trained models as starting points
   - Fine-tuning models for specific network conditions
   - Sharing models across similar network deployments

## Extending the ML xApps

### Adding New Metrics

To add support for new metrics:

1. Modify the metrics list in the command-line arguments
2. Update the data processing logic in the callback functions
3. Extend feature extraction for ML models

### Adding New ML Models

To add new ML models:

1. Import required libraries in the xApp
2. Add model training functions
3. Implement prediction methods
4. Integrate with control logic

### Customizing Control Actions

To customize control actions:

1. Modify the control logic in the xApp
2. Use different E2SM-RC actions
3. Implement new control strategies

## Risk Disclaimer

**Use at Your Own Risk**: These ML-enhanced xApps are provided for educational and research purposes only. The user assumes full responsibility for any potential risks, including but not limited to hardware damage, data loss, network disruption, or any other adverse effects that may result from the use of these xApps. The developers and contributors disclaim all warranties, express or implied, and shall not be liable for any damages arising from the use of these xApps.

## License

This software is licensed under the same terms as the original O-RAN SC RIC repository. See the LICENSE file for details.