#!/usr/bin/env python3

import time
import datetime
import argparse
import signal
import numpy as np
from collections import deque, defaultdict
from lib.xAppBase import xAppBase


class QoSTrafficSteererXapp(xAppBase):
    def __init__(self, http_server_port, rmr_port):
        super(QoSTrafficSteererXapp, self).__init__('', http_server_port, rmr_port)
        
        # Traffic classification and QoS profiles
        self.qos_profiles = {
            'voice': {'latency_ms': 10, 'bandwidth_mbps': 0.1, 'priority': 1},
            'video': {'latency_ms': 30, 'bandwidth_mbps': 5, 'priority': 2},
            'gaming': {'latency_ms': 20, 'bandwidth_mbps': 1, 'priority': 1},
            'web': {'latency_ms': 100, 'bandwidth_mbps': 10, 'priority': 3},
            'file_transfer': {'latency_ms': 500, 'bandwidth_mbps': 50, 'priority': 4}
        }
        
        # UE traffic classification history
        self.ue_traffic_history = defaultdict(lambda: deque(maxlen=50))
        self.ue_qos_violations = defaultdict(int)
        
        # Network state
        self.cell_load = {}  # Track load per cell
        self.ue_cell_mapping = {}  # Track which cell each UE is connected to
        
        # Steering parameters
        self.load_threshold = 0.8  # 80% load threshold for offloading
        self.qos_violation_threshold = 3  # Number of violations before steering
        self.steering_cooldown = 120  # 2 minutes between steering actions per UE
        self.last_steering_time = {}

    def classify_traffic(self, ue_id, metrics_data):
        """Classify traffic type based on metrics patterns"""
        # Add current metrics to history
        self.ue_traffic_history[ue_id].append(metrics_data)
        
        # Need sufficient history for classification
        if len(self.ue_traffic_history[ue_id]) < 10:
            return 'unknown'
            
        history = list(self.ue_traffic_history[ue_id])
        
        # Extract key metrics
        dl_throughputs = []
        ul_throughputs = []
        
        for metrics in history[-10:]:  # Last 10 samples
            if 'DRB.UEThpDl' in metrics:
                dl_throughputs.extend(metrics['DRB.UEThpDl'])
            if 'DRB.UEThpUl' in metrics:
                ul_throughputs.extend(metrics['DRB.UEThpUl'])
        
        if not dl_throughputs or not ul_throughputs:
            return 'unknown'
            
        avg_dl = np.mean(dl_throughputs)
        avg_ul = np.mean(ul_throughputs)
        dl_variance = np.var(dl_throughputs) if len(dl_throughputs) > 1 else 0
        ul_variance = np.var(ul_throughputs) if len(ul_throughputs) > 1 else 0
        
        # Simple traffic classification based on throughput patterns
        if avg_dl < 0.5 and avg_ul < 0.5 and dl_variance < 1 and ul_variance < 1:
            return 'voice'  # Low, steady throughput
        elif avg_dl > 20 and dl_variance > 100:
            return 'video'  # High, variable DL throughput
        elif avg_ul > 2 and ul_variance > 10:
            return 'gaming'  # Interactive, variable UL
        elif avg_dl > 1 and avg_dl < 20:
            return 'web'  # Moderate browsing
        elif avg_dl > 50:
            return 'file_transfer'  # High throughput
        else:
            return 'unknown'

    def check_qos_violations(self, ue_id, traffic_type, metrics_data):
        """Check if current metrics violate QoS requirements"""
        if traffic_type == 'unknown':
            return False
            
        qos_profile = self.qos_profiles[traffic_type]
        
        # Check throughput violations
        if 'DRB.UEThpDl' in metrics_data and metrics_data['DRB.UEThpDl']:
            current_dl = sum(metrics_data['DRB.UEThpDl'])
            if current_dl < qos_profile['bandwidth_mbps'] * 0.5:  # Below 50% of required
                self.ue_qos_violations[ue_id] += 1
                return True
                
        if 'DRB.UEThpUl' in metrics_data and metrics_data['DRB.UEThpUl']:
            current_ul = sum(metrics_data['DRB.UEThpUl'])
            if current_ul < qos_profile['bandwidth_mbps'] * 0.3:  # Below 30% of required
                self.ue_qos_violations[ue_id] += 1
                return True
                
        return False

    def evaluate_cell_load(self, e2_agent_id, metrics_data):
        """Evaluate current cell load based on metrics"""
        # Simple load estimation based on resource utilization
        load_indicators = []
        
        # Check various metrics that indicate load
        if 'DRB.UEThpDl' in metrics_data:
            dl_load = sum(metrics_data['DRB.UEThpDl']) / 1000.0  # Normalize
            load_indicators.append(min(dl_load, 1.0))
            
        if 'DRB.UEThpUl' in metrics_data:
            ul_load = sum(metrics_data['DRB.UEThpUl']) / 1000.0  # Normalize
            load_indicators.append(min(ul_load, 1.0))
            
        if 'RRC.ConnEstabSucc' in metrics_data:
            # Connection success rate can indicate congestion
            conn_rate = metrics_data['RRC.ConnEstabSucc'][0] if metrics_data['RRC.ConnEstabSucc'] else 0
            # Lower success rate indicates higher load
            load_indicators.append(1.0 - (conn_rate / 100.0) if conn_rate > 0 else 0)
            
        if load_indicators:
            avg_load = np.mean(load_indicators)
            self.cell_load[e2_agent_id] = avg_load
            return avg_load
        else:
            self.cell_load[e2_agent_id] = 0.0
            return 0.0

    def should_steer_ue(self, ue_id, current_cell_load, traffic_type):
        """Determine if UE should be steered to another cell"""
        current_time = time.time()
        last_steer = self.last_steering_time.get(ue_id, 0)
        
        # Check cooldown period
        if (current_time - last_steer) < self.steering_cooldown:
            return False
            
        # Check if QoS violations exceed threshold
        if self.ue_qos_violations[ue_id] < self.qos_violation_threshold:
            return False
            
        # Check if current cell is overloaded and UE has high priority traffic
        if current_cell_load > self.load_threshold:
            qos_profile = self.qos_profiles.get(traffic_type, {'priority': 5})
            if qos_profile['priority'] <= 2:  # High priority traffic
                return True
                
        return False

    def my_subscription_callback(self, e2_agent_id, subscription_id, indication_hdr, indication_msg, kpm_report_style, ue_id):
        indication_hdr = self.e2sm_kpm.extract_hdr_info(indication_hdr)
        meas_data = self.e2sm_kpm.extract_meas_data(indication_msg)

        current_time = datetime.datetime.now()
        print(f"\n[{current_time.strftime('%H:%M:%S')}] QoS Traffic Steerer - Monitoring:")
        print("  E2SM_KPM RIC Indication Content:")
        print("  -CollectionStartTime: ", indication_hdr['colletStartTime'])

        # Update cell load
        cell_load = self.evaluate_cell_load(e2_agent_id, meas_data.get("measData", {}))
        print(f"  --Cell {e2_agent_id} Load: {cell_load:.2f}")

        # Process UE-level metrics
        if "ueMeasData" in meas_data:
            for ue_id, ue_meas_data in meas_data["ueMeasData"].items():
                print(f"  --UE_id: {ue_id}")
                
                # Extract metrics for processing
                metrics_summary = {}
                for metric_name, values in ue_meas_data["measData"].items():
                    metrics_summary[metric_name] = values
                    print(f"  ---Metric: {metric_name}, Value: {sum(values) if values else 0}")

                # Classify traffic type
                traffic_type = self.classify_traffic(ue_id, metrics_summary)
                print(f"  ---Traffic Type: {traffic_type}")
                
                # Check QoS violations
                qos_violated = self.check_qos_violations(ue_id, traffic_type, metrics_summary)
                if qos_violated:
                    print(f"  *** QoS VIOLATION DETECTED for {traffic_type} traffic ***")
                
                # Update UE-cell mapping
                self.ue_cell_mapping[ue_id] = e2_agent_id
                
                # Check if steering is needed
                if self.should_steer_ue(ue_id, cell_load, traffic_type):
                    print(f"  *** STEERING RECOMMENDED for UE {ue_id} ***")
                    print(f"      Traffic: {traffic_type}, QoS Violations: {self.ue_qos_violations[ue_id]}")
                    print(f"      Current Cell Load: {cell_load:.2f}")
                    
                    # In a real implementation, we would identify target cells
                    # and trigger handover. For now, we'll just log the decision.
                    print(f"      [ACTION] Would steer UE {ue_id} to less congested cell")
                    
                    # Update steering time
                    self.last_steering_time[ue_id] = time.time()
                    
                    # Reset violation counter after steering attempt
                    self.ue_qos_violations[ue_id] = 0

        print("------------------------------------------------------------------")

    @xAppBase.start_function
    def start(self, e2_node_id, kpm_report_style, ue_ids, metric_names):
        report_period = 3000  # 3 seconds for stable traffic analysis
        granul_period = 3000

        subscription_callback = lambda agent, sub, hdr, msg: self.my_subscription_callback(agent, sub, hdr, msg, kpm_report_style, None)

        # Matching conditions for UEs
        matchingUeConds = [{'testCondInfo': {'testType': ('ul-rSRP', 'true'), 'testExpr': 'lessthan', 'testValue': ('valueInt', 1000)}}]
        
        print(f"Subscribe to E2 node ID: {e2_node_id}, RAN func: e2sm_kpm, Report Style: {kpm_report_style}, metrics: {metric_names}")
        self.e2sm_kpm.subscribe_report_service_style_4(e2_node_id, report_period, matchingUeConds, metric_names, granul_period, subscription_callback)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='QoS-Aware Traffic Steering xApp')
    parser.add_argument("--http_server_port", type=int, default=8097, help="HTTP server listen port")
    parser.add_argument("--rmr_port", type=int, default=4567, help="RMR port")
    parser.add_argument("--e2_node_id", type=str, default='gnbd_001_001_00019b_0', help="E2 Node ID")
    parser.add_argument("--ran_func_id", type=int, default=2, help="RAN function ID")
    parser.add_argument("--kpm_report_style", type=int, default=4, help="KPM Report Style ID")
    parser.add_argument("--ue_ids", type=str, default='0', help="UE ID")
    parser.add_argument("--metrics", type=str, default='DRB.UEThpDl,DRB.UEThpUl,RRC.ConnEstabSucc', help="Metrics name as comma-separated string")

    args = parser.parse_args()
    e2_node_id = args.e2_node_id
    ran_func_id = args.ran_func_id
    ue_ids = list(map(int, args.ue_ids.split(",")))
    kpm_report_style = args.kpm_report_style
    metrics = args.metrics.split(",")

    # Create xApp
    myXapp = QoSTrafficSteererXapp(args.http_server_port, args.rmr_port)
    myXapp.e2sm_kpm.set_ran_func_id(ran_func_id)

    # Connect exit signals
    signal.signal(signal.SIGQUIT, myXapp.signal_handler)
    signal.signal(signal.SIGTERM, myXapp.signal_handler)
    signal.signal(signal.SIGINT, myXapp.signal_handler)

    # Start xApp
    myXapp.start(e2_node_id, kpm_report_style, ue_ids, metrics)