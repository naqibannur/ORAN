#!/usr/bin/env python3

import time
import datetime
import argparse
import signal
import numpy as np
from collections import deque
from scipy import stats
from lib.xAppBase import xAppBase


class AnomalyDetectorXapp(xAppBase):
    def __init__(self, http_server_port, rmr_port):
        super(AnomalyDetectorXapp, self).__init__('', http_server_port, rmr_port)
        
        # Data storage for statistical analysis
        self.metrics_history = {}  # Store historical metrics
        self.max_history_length = 200  # Keep last 200 data points
        
        # Anomaly detection parameters
        self.anomaly_threshold = 3.0  # Z-score threshold
        self.min_history_for_detection = 30  # Minimum samples needed
        self.alert_cooldown = 60  # Seconds between alerts for same metric
        self.last_alert_time = {}  # Track when last alert was sent for each metric
        
        # Performance counters
        self.anomalies_detected = 0
        self.anomaly_details = {}

    def update_metrics_history(self, metric_name, value):
        """Update historical data for a metric"""
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = deque(maxlen=self.max_history_length)
        
        self.metrics_history[metric_name].append(value)

    def detect_anomaly(self, metric_name, current_value):
        """Detect if current value is anomalous using Z-score"""
        if metric_name not in self.metrics_history:
            return False, 0.0
            
        history = list(self.metrics_history[metric_name])
        
        # Need sufficient history for meaningful statistics
        if len(history) < self.min_history_for_detection:
            return False, 0.0
            
        # Calculate Z-score
        mean_val = np.mean(history)
        std_val = np.std(history)
        
        if std_val == 0:
            return False, 0.0
            
        z_score = abs(current_value - mean_val) / std_val
        
        # Check if anomaly and if cooldown period has passed
        current_time = time.time()
        last_alert = self.last_alert_time.get(metric_name, 0)
        
        is_anomaly = z_score > self.anomaly_threshold
        cooldown_expired = (current_time - last_alert) > self.alert_cooldown
        
        if is_anomaly and cooldown_expired:
            self.last_alert_time[metric_name] = current_time
            self.anomalies_detected += 1
            
            if metric_name not in self.anomaly_details:
                self.anomaly_details[metric_name] = 0
            self.anomaly_details[metric_name] += 1
            
            return True, z_score
        elif is_anomaly:
            # Anomaly detected but in cooldown period
            return False, z_score
        else:
            return False, z_score

    def my_subscription_callback(self, e2_agent_id, subscription_id, indication_hdr, indication_msg, kpm_report_style, ue_id):
        indication_hdr = self.e2sm_kpm.extract_hdr_info(indication_hdr)
        meas_data = self.e2sm_kpm.extract_meas_data(indication_msg)

        current_time = datetime.datetime.now()
        print(f"\n[{current_time.strftime('%H:%M:%S')}] Anomaly Detector - Monitoring Network Performance:")
        print("  E2SM_KPM RIC Indication Content:")
        print("  -CollectionStartTime: ", indication_hdr['colletStartTime'])

        anomalies_found = []

        # Process UE-level metrics
        if "ueMeasData" in meas_data:
            for ue_id, ue_meas_data in meas_data["ueMeasData"].items():
                print(f"  --UE_id: {ue_id}")
                
                # Process each metric
                for metric_name, values in ue_meas_data["measData"].items():
                    if values:  # Ensure we have values
                        # Aggregate values if multiple samples
                        current_value = sum(values) if isinstance(values, list) else values
                        
                        # Update history
                        self.update_metrics_history(f"{ue_id}_{metric_name}", current_value)
                        
                        # Detect anomalies
                        is_anomaly, z_score = self.detect_anomaly(f"{ue_id}_{metric_name}", current_value)
                        
                        print(f"  ---Metric: {metric_name}, Value: {current_value}, Z-Score: {z_score:.2f}")
                        
                        if is_anomaly:
                            anomalies_found.append({
                                'ue_id': ue_id,
                                'metric': metric_name,
                                'value': current_value,
                                'z_score': z_score
                            })
                            print(f"  *** ANOMALY DETECTED *** {metric_name} for UE {ue_id} (Z-score: {z_score:.2f})")

        # Process cell-level metrics (Format 1)
        elif "measData" in meas_data:
            print("  --Cell-level metrics:")
            for metric_name, values in meas_data["measData"].items():
                if values:
                    current_value = sum(values) if isinstance(values, list) else values
                    
                    # Update history
                    self.update_metrics_history(f"cell_{metric_name}", current_value)
                    
                    # Detect anomalies
                    is_anomaly, z_score = self.detect_anomaly(f"cell_{metric_name}", current_value)
                    
                    print(f"  ---Metric: {metric_name}, Value: {current_value}, Z-Score: {z_score:.2f}")
                    
                    if is_anomaly:
                        anomalies_found.append({
                            'ue_id': 'cell',
                            'metric': metric_name,
                            'value': current_value,
                            'z_score': z_score
                        })
                        print(f"  *** ANOMALY DETECTED *** {metric_name} at cell level (Z-score: {z_score:.2f})")

        # Report anomalies
        if anomalies_found:
            print(f"\n  *** ANOMALY SUMMARY ***")
            for anomaly in anomalies_found:
                print(f"    UE: {anomaly['ue_id']}, Metric: {anomaly['metric']}, Value: {anomaly['value']}, Severity: {anomaly['z_score']:.2f}")
            
            # Trigger corrective actions based on anomaly type
            self.handle_anomalies(e2_agent_id, anomalies_found)

        # Print statistics
        print(f"  Performance Stats - Total Anomalies Detected: {self.anomalies_detected}")
        for metric, count in self.anomaly_details.items():
            print(f"    {metric}: {count} anomalies")

        print("------------------------------------------------------------------")

    def handle_anomalies(self, e2_agent_id, anomalies):
        """Handle detected anomalies with appropriate actions"""
        for anomaly in anomalies:
            metric_name = anomaly['metric']
            ue_id = anomaly['ue_id']
            severity = anomaly['z_score']
            
            # Example actions based on metric type
            if "UEThpDl" in metric_name and ue_id != 'cell':
                # Low downlink throughput
                if anomaly['value'] < 10:  # Very low throughput
                    print(f"    Taking corrective action for low DL throughput on UE {ue_id}")
                    # Could trigger handover to better cell
                    # self.trigger_handover(e2_agent_id, ue_id)
                    
            elif "UEThpUl" in metric_name and ue_id != 'cell':
                # Low uplink throughput
                if anomaly['value'] < 5:  # Very low throughput
                    print(f"    Taking corrective action for low UL throughput on UE {ue_id}")
                    # Could adjust power settings or PRB allocation
                    
            elif "RRC" in metric_name:
                # RRC connection issues
                print(f"    Monitoring RRC connection issues for cell")
                # Could adjust cell parameters

    def trigger_handover(self, e2_agent_id, ue_id):
        """Trigger handover to a better cell (example implementation)"""
        # This would require more sophisticated logic to determine target cell
        print(f"    [ACTION] Would trigger handover for UE {ue_id} from {e2_agent_id}")
        # In practice, would use self.e2sm_rc.control_handover() with appropriate parameters

    @xAppBase.start_function
    def start(self, e2_node_id, kpm_report_style, ue_ids, metric_names):
        report_period = 1000  # 1 second for responsive anomaly detection
        granul_period = 1000

        subscription_callback = lambda agent, sub, hdr, msg: self.my_subscription_callback(agent, sub, hdr, msg, kpm_report_style, None)

        # Matching conditions for UEs
        matchingUeConds = [{'testCondInfo': {'testType': ('ul-rSRP', 'true'), 'testExpr': 'lessthan', 'testValue': ('valueInt', 1000)}}]
        
        print(f"Subscribe to E2 node ID: {e2_node_id}, RAN func: e2sm_kpm, Report Style: {kpm_report_style}, metrics: {metric_names}")
        self.e2sm_kpm.subscribe_report_service_style_4(e2_node_id, report_period, matchingUeConds, metric_names, granul_period, subscription_callback)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Network Anomaly Detector xApp')
    parser.add_argument("--http_server_port", type=int, default=8096, help="HTTP server listen port")
    parser.add_argument("--rmr_port", type=int, default=4566, help="RMR port")
    parser.add_argument("--e2_node_id", type=str, default='gnbd_001_001_00019b_0', help="E2 Node ID")
    parser.add_argument("--ran_func_id", type=int, default=2, help="RAN function ID")
    parser.add_argument("--kpm_report_style", type=int, default=4, help="KPM Report Style ID")
    parser.add_argument("--ue_ids", type=str, default='0', help="UE ID")
    parser.add_argument("--metrics", type=str, default='DRB.UEThpDl,DRB.UEThpUl,RRC.ConnEstabSucc,DRB.PdcpSduVolumeDL', help="Metrics name as comma-separated string")

    args = parser.parse_args()
    e2_node_id = args.e2_node_id
    ran_func_id = args.ran_func_id
    ue_ids = list(map(int, args.ue_ids.split(",")))
    kpm_report_style = args.kpm_report_style
    metrics = args.metrics.split(",")

    # Create xApp
    myXapp = AnomalyDetectorXapp(args.http_server_port, args.rmr_port)
    myXapp.e2sm_kpm.set_ran_func_id(ran_func_id)

    # Connect exit signals
    signal.signal(signal.SIGQUIT, myXapp.signal_handler)
    signal.signal(signal.SIGTERM, myXapp.signal_handler)
    signal.signal(signal.SIGINT, myXapp.signal_handler)

    # Start xApp
    myXapp.start(e2_node_id, kpm_report_style, ue_ids, metrics)